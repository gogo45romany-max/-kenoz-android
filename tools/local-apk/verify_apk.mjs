import fs from 'node:fs';
import crypto from 'node:crypto';

const apkPath = process.argv[2];
const apk = fs.readFileSync(apkPath);
console.log('file:', apkPath, apk.length, 'bytes');

function findEOCD(buf) {
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65558); i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) return i;
  }
  return -1;
}

const eocdOff = findEOCD(apk);
if (eocdOff < 0) throw new Error('no EOCD');
const cdSize = apk.readUInt32LE(eocdOff + 12);
const cdOff = apk.readUInt32LE(eocdOff + 16);
const cdEnd = cdOff + cdSize;
console.log('EOCD at', eocdOff, '| CD off', cdOff, '| CD size', cdSize, '| entries end', cdEnd);

// ---- signing block
const MAGIC = Buffer.from('APK Sig Block 42', 'utf8');
if (!apk.subarray(cdOff - 16, cdOff).equals(MAGIC)) throw new Error('no APK Signature Scheme block');
const size2 = Number(apk.readBigUInt64LE(cdOff - 24));
const blockStart = cdOff - size2 - 8;
const size1 = Number(apk.readBigUInt64LE(blockStart));
console.log('signing block: start', blockStart, 'size1', size1, 'size2', size2, size1 === size2 ? '(sizes agree)' : '(MISMATCH)');

let p = blockStart + 8;
const pairs = [];
while (p < cdOff - 24) {
  const len = Number(apk.readBigUInt64LE(p));
  const id = apk.readUInt32LE(p + 8);
  const value = apk.subarray(p + 12, p + 8 + len);
  pairs.push({ id: '0x' + id.toString(16), value });
  p += 8 + len;
}
console.log('pairs:', pairs.map(x => `${x.id} (${x.value.length}B)`).join(', '));

class Reader {
  constructor(buf) { this.b = buf; this.o = 0; }
  u32() { const v = this.b.readUInt32LE(this.o); this.o += 4; return v; }
  lp() { const n = this.u32(); const s = this.b.subarray(this.o, this.o + n); this.o += n; return s; }
  done() { return this.o >= this.b.length; }
}

const v2 = pairs.find(x => x.id === '0x7109871a');
if (!v2) throw new Error('no v2 signature');
const outer = new Reader(v2.value);
const signersRaw = outer.lp();          // sequence of signers
const signers = new Reader(signersRaw);
const sr = new Reader(signers.lp());    // first signer
const signedData = sr.lp();
const signatures = sr.lp();
const publicKey = sr.lp();
console.log('v2 signer: signedData', signedData.length, 'B | signatures', signatures.length, 'B | publicKey', publicKey.length, 'B');

// signed data
const sd = new Reader(signedData);
const digestsSeq = new Reader(sd.lp());
const certsSeq = new Reader(sd.lp());
const attrs = sd.lp();

const digests = [];
while (!digestsSeq.done()) {
  const rec = new Reader(digestsSeq.lp());
  const alg = rec.u32();
  digests.push({ alg: '0x' + alg.toString(16), digest: rec.lp() });
}
const certs = [];
while (!certsSeq.done()) certs.push(certsSeq.lp());
console.log('digests:', digests.map(d => `${d.alg}:${d.digest.length}B`).join(', '), '| certs:', certs.length, '| attrs:', attrs.length);

// signatures
const sigsSeq = new Reader(signatures);
const sigs = [];
while (!sigsSeq.done()) {
  const rec = new Reader(sigsSeq.lp());
  const alg = rec.u32();
  sigs.push({ alg: '0x' + alg.toString(16), sig: rec.lp() });
}
console.log('signature algs:', sigs.map(s => `${s.alg}:${s.sig.length}B`).join(', '));

// ---- chunked content digest (SHA-256), per AOSP: each segment chunked separately
const CHUNK = 1048576;
const eocdCopy = Buffer.from(apk.subarray(eocdOff));
eocdCopy.writeUInt32LE(blockStart, 16); // offset of start of CD as if block absent
const segments = [apk.subarray(0, blockStart), apk.subarray(cdOff, cdEnd), eocdCopy];
const chunkDigests = [];
for (const seg of segments) {
  for (let i = 0; i < seg.length; i += CHUNK) {
    const c = seg.subarray(i, Math.min(i + CHUNK, seg.length));
    const hh = crypto.createHash('sha256');
    hh.update(Buffer.from([0xa5]));
    const lenBuf = Buffer.alloc(4); lenBuf.writeUInt32LE(c.length);
    hh.update(lenBuf); hh.update(c);
    chunkDigests.push(hh.digest());
  }
}
const top = crypto.createHash('sha256');
top.update(Buffer.from([0x5a]));
const cnt = Buffer.alloc(4); cnt.writeUInt32LE(chunkDigests.length);
top.update(cnt);
for (const d of chunkDigests) top.update(d);
const computed = top.digest();
const expected = digests.find(d => d.alg === '0x0103') || digests[0];
console.log('chunks:', chunkDigests.length, '| segments:', segments.map(x => x.length).join('/'));
console.log('computed :', computed.toString('hex'));
console.log('in apk   :', expected.digest.toString('hex'));
if (!computed.equals(expected.digest)) throw new Error('CONTENT DIGEST MISMATCH');

// ---- RSA signature verification over signedData using the certificate public key
const forge = (await import('node-forge')).default;
const cert = forge.pki.certificateFromAsn1(forge.asn1.fromDer(forge.util.createBuffer(certs[0].toString('binary'))));
const md = forge.md.sha256.create();
md.update(signedData.toString('binary'));
const pkcs1Sig = sigs.find(s => s.alg === '0x0103') || sigs[0];
const sigOk = cert.publicKey.verify(md.digest().getBytes(), pkcs1Sig.sig.toString('binary'));
console.log('signature valid:', sigOk);
if (!sigOk) throw new Error('SIGNATURE INVALID');

// public key in block must equal the certificate's SubjectPublicKeyInfo
const blockKey = crypto.createPublicKey({ key: Buffer.from(publicKey), format: 'der', type: 'spki' });
const certX = new crypto.X509Certificate(Buffer.from(certs[0]));
const certSpki = certX.publicKey.export({ type: 'spki', format: 'der' });
const same = Buffer.from(publicKey).equals(certSpki) && blockKey.asymmetricKeyType === 'rsa';
console.log('block public key is X.509 SPKI matching certificate:', same, '| type:', blockKey.asymmetricKeyType);
if (!same) throw new Error('PUBLIC KEY MISMATCH');

console.log('cert subject CN:', cert.subject.getField('CN')?.value, '| valid to:', cert.validity.notAfter.toISOString());

console.log('\nV2 SIGNATURE VERIFIED OK');
