/**
 * Minimal, spec-faithful APK Signature Scheme v2 signer.
 * (The npm library writes a PKCS#1 public key where Android requires
 *  SubjectPublicKeyInfo, so we build the block ourselves.)
 */
import fs from 'node:fs';
import crypto from 'node:crypto';
import forge from 'node-forge';

const [,, apkIn, apkOut, p12Path, pass] = process.argv;

// ---------- key material ----------
const p12 = forge.pkcs12.pkcs12FromAsn1(
  forge.asn1.fromDer(forge.util.createBuffer(fs.readFileSync(p12Path).toString('binary'))), pass);
const keyBags = p12.getBags({ bagType: forge.pki.oids.pkcs8ShroudedKeyBag })[forge.pki.oids.pkcs8ShroudedKeyBag];
const certBags = p12.getBags({ bagType: forge.pki.oids.certBag })[forge.pki.oids.certBag];
const privateKey = keyBags[0].key;
const cert = certBags[0].cert;

const keyPem = forge.pki.privateKeyToPem(privateKey);            // PKCS#1 — fine for node crypto
const certDer = Buffer.from(forge.asn1.toDer(forge.pki.certificateToAsn1(cert)).getBytes(), 'binary');
const spkiDer = Buffer.from(forge.asn1.toDer(forge.pki.publicKeyToAsn1(cert.publicKey)).getBytes(), 'binary');
console.log('cert DER', certDer.length, 'B | raw RSAPublicKey DER', spkiDer.length, 'B');

// build proper SubjectPublicKeyInfo from the certificate
const certObj = new crypto.X509Certificate(certDer);
const spki = certObj.publicKey.export({ type: 'spki', format: 'der' });
console.log('SPKI', spki.length, 'B | subject', certObj.subject.replace(/\n/g, ', '));

// ---------- input apk ----------
const apk = fs.readFileSync(apkIn);
function findEOCD(buf) {
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65558); i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) return i;
  }
  return -1;
}
const eocdOff = findEOCD(apk);
const cdSize = apk.readUInt32LE(eocdOff + 12);
const cdOff = apk.readUInt32LE(eocdOff + 16);
if (cdOff + cdSize !== eocdOff) throw new Error('unexpected zip layout (zip64 / comment)');
console.log('EOCD', eocdOff, '| CD', cdOff, '+', cdSize);

// ---------- chained content digest (per AOSP: one chunk chain per segment) ----------
const CHUNK = 1048576;
const segments = [
  apk.subarray(0, cdOff),        // ZIP entries
  apk.subarray(cdOff, eocdOff),  // central directory
  apk.subarray(eocdOff),         // EOCD (CD offset already == signing block offset)
];
const chunkDigests = [];
for (const seg of segments) {
  for (let i = 0; i < seg.length; i += CHUNK) {
    const c = seg.subarray(i, Math.min(i + CHUNK, seg.length));
    const h = crypto.createHash('sha256');
    h.update(Buffer.from([0xa5]));
    const len = Buffer.alloc(4); len.writeUInt32LE(c.length);
    h.update(len); h.update(c);
    chunkDigests.push(h.digest());
  }
}
const top = crypto.createHash('sha256');
top.update(Buffer.from([0x5a]));
const cnt = Buffer.alloc(4); cnt.writeUInt32LE(chunkDigests.length);
top.update(cnt);
for (const d of chunkDigests) top.update(d);
const contentDigest = top.digest();
console.log('chunks', chunkDigests.length, '| sha256 content digest', contentDigest.toString('hex'));

// ---------- DV encoding helpers ----------
const u32 = n => { const b = Buffer.alloc(4); b.writeUInt32LE(n); return b; };
const lp = buf => Buffer.concat([u32(buf.length), buf]);
const lpSeq = items => lp(Buffer.concat(items.map(lp)));

const SIG_ALG_RSA_PKCS1_SHA256 = 0x0103;
const digestRecord = Buffer.concat([u32(SIG_ALG_RSA_PKCS1_SHA256), lp(contentDigest)]);
const signedData = Buffer.concat([
  lpSeq([digestRecord]),   // digests
  lpSeq([certDer]),        // certificates
  lp(Buffer.alloc(0)),     // additional attributes
]);

const signature = crypto.sign('sha256', signedData, {
  key: forge.pki.privateKeyToPem(privateKey),
  padding: crypto.constants.RSA_PKCS1_PADDING,
});
console.log('signature', signature.length, 'B');

const signer = Buffer.concat([
  lp(signedData),
  lpSeq([Buffer.concat([u32(SIG_ALG_RSA_PKCS1_SHA256), lp(signature)])]),
  lp(spki),
]);
const v2Value = lpSeq([signer]);              // sequence of signers
const pairId = Buffer.alloc(4); pairId.writeUInt32LE(0x7109871a);
const pairLen = Buffer.alloc(8); pairLen.writeBigUInt64LE(BigInt(4 + v2Value.length));
const pair = Buffer.concat([pairLen, pairId, v2Value]);

// APK Signing Block: [u64 size][pairs][u64 size][magic]
const blockSize = 8 + pair.length + 16;        // pairs + trailing size field + magic
const sizeField = Buffer.alloc(8); sizeField.writeBigUInt64LE(BigInt(blockSize));
const MAGIC = Buffer.from('APK Sig Block 42', 'utf8');
const block = Buffer.concat([sizeField, pair, sizeField, MAGIC]);
console.log('v2 pair', pair.length, 'B | signing block', block.length, 'B');
// ---------- assemble ----------
const eocd = Buffer.from(apk.subarray(eocdOff));
const newCdOff = cdOff + block.length;
eocd.writeUInt32LE(newCdOff, 16);
const out = Buffer.concat([apk.subarray(0, cdOff), block, apk.subarray(cdOff, eocdOff), eocd]);
fs.writeFileSync(apkOut, out);
console.log('wrote', apkOut, out.length, 'bytes (CD now at', newCdOff + ')');

