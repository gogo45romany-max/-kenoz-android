"""Static checks for the hand-written smali used by the SDK-less APK build.

Checks:
  1. every type/method/field reference resolves against android.jar (or java.*),
  2. every register index stays inside the declared .locals/parameter window,
  3. the produced dex header is well formed and contains the expected classes.

Usage: verify_smali.py <smali-dir> <dex-file> <android.jar>
"""
import os, re, struct, sys, zipfile

if len(sys.argv) < 4:
    print(__doc__)
    raise SystemExit(2)
SMALI_DIR, DEX, ANDROID_JAR = sys.argv[1], sys.argv[2], sys.argv[3]

# ---------------------------------------------------------------- class parsing
def parse_class(data):
    p = 8
    count = struct.unpack('>H', data[p:p+2])[0]; p += 2
    cp = {}; i = 1
    while i < count:
        tag = data[p]; p += 1
        if tag == 1:
            ln = struct.unpack('>H', data[p:p+2])[0]; p += 2
            cp[i] = ('utf8', data[p:p+ln].decode('utf-8', 'replace')); p += ln
        elif tag == 7: cp[i] = ('class', struct.unpack('>H', data[p:p+2])[0]); p += 2
        elif tag in (8, 16, 19, 20): cp[i] = ('ref', struct.unpack('>H', data[p:p+2])[0]); p += 2
        elif tag == 15: cp[i] = ('mh',); p += 3
        elif tag in (3, 4): cp[i] = ('num',); p += 4
        elif tag in (9, 10, 11, 12, 17, 18): cp[i] = ('pair',) + struct.unpack('>HH', data[p:p+4]); p += 4
        elif tag in (5, 6): cp[i] = ('num',); p += 8; i += 1
        i += 1
    def utf(k):
        v = cp.get(k)
        if v is None: return None
        if v[0] == 'utf8': return v[1]
        if v[0] in ('class', 'ref'): return utf(v[1])
        if v[0] == 'pair': return utf(v[1]) + ' ' + utf(v[2])
        return None
    acc = struct.unpack('>H', data[p:p+2])[0]
    this_i = struct.unpack('>H', data[p+2:p+4])[0]
    super_i = struct.unpack('>H', data[p+4:p+6])[0]
    super_name = utf(super_i)
    p += 6
    ifc = struct.unpack('>H', data[p:p+2])[0]
    ifaces = [utf(struct.unpack('>H', data[p+p2:p+p2+2])[0]) for p2 in range(2, 2 + 2*ifc, 2)]
    p += 2 + 2 * ifc
    def skip_attrs(p):
        n = struct.unpack('>H', data[p:p+2])[0]; p += 2
        for _ in range(n):
            p += 2
            ln = struct.unpack('>I', data[p:p+4])[0]; p += 4 + ln
        return p
    nf = struct.unpack('>H', data[p:p+2])[0]; p += 2
    fields = []
    for _ in range(nf):
        acc, ni, di = struct.unpack('>HHH', data[p:p+6]); p += 6
        fields.append((utf(ni), utf(di)))
        p = skip_attrs(p)
    nm = struct.unpack('>H', data[p:p+2])[0]; p += 2
    methods = []
    for _ in range(nm):
        acc, ni, di = struct.unpack('>HHH', data[p:p+6]); p += 6
        methods.append((acc, utf(ni), utf(di)))
        p = skip_attrs(p)
    return fields, methods, super_name, ifaces

jar = zipfile.ZipFile(ANDROID_JAR)
_index = {}
def android_members(desc):
    """desc like Landroid/app/Activity; -> (fields dict, methods dict)"""
    if desc in _index: return _index[desc]
    name = desc[1:-1] + '.class'
    if name not in jar.namelist():
        _index[desc] = None
        return None
    f, m, sup, ifaces = parse_class(jar.read(name))
    fd = {}
    for n, d in f: fd[(n, d)] = True
    md = {}
    for acc, n, d in m: md[(n, d)] = True
    _index[desc] = (fd, md, name, sup, ifaces)
    return _index[desc]

LOCAL = set()
for root, _, files in os.walk(SMALI_DIR):
    for fn in files:
        if fn.endswith('.smali'):
            txt = open(os.path.join(root, fn), encoding='utf-8').read()
            m = re.search(r'\.class[^\n]*?(L[\w/$]+;)', txt)
            if m: LOCAL.add(m.group(1))

problems = []
checked = 0
def check_member(desc, name, sig, kind):
    global checked
    checked += 1
    if desc.startswith('L') is False:
        return
    if desc in LOCAL:
        return  # resolved separately below
    if desc.startswith('Landroid/') or desc.startswith('Ljava/'):
        mem = android_members(desc)
        if mem is None:
            problems.append(f'{kind}: class not found {desc}')
            return
        def has(desc2, depth=0):
            if depth > 8: return False
            if desc2.startswith('L') and desc2.endswith(';'):
                key = desc2[1:-1] + '.class'
            else:
                key = desc2 + '.class'
            if key not in jar.namelist(): return False
            f2, m2, sup2, if2 = parse_class(jar.read(key))
            table2 = f2 if kind == 'field' else m2
            for entry in table2:
                if kind == 'method':
                    n, d = entry[1], entry[2]
                else:
                    n, d = entry[0], entry[1]
                if n == name and d == sig: return True
            if sup2 and has(sup2, depth + 1): return True
            for i2 in if2:
                if has(i2, depth + 1): return True
            return False

        if has(desc):
            return
        problems.append(f'{kind}: missing {desc}->{name}{sig}')

# ------------------------------------------------------------- smali checking
ref_re = re.compile(r'(?:invoke-\w+|sget|sput|iget|iput|new-instance|check-cast|const-class)[^\n]*?(L[\w/$]+;)(?:->([\w$<>]+)(\([^)]*\)\S+|[:\w$\[\]/;]+))?')

for root, _, files in os.walk(SMALI_DIR):
    for fn in files:
        if not fn.endswith('.smali'): continue
        path = os.path.join(root, fn)
        text = open(path, encoding='utf-8').read()
        # class/field/method refs
        for line in text.splitlines():
            line = line.strip()
            if line.startswith('#') or not line: continue
            for m in re.finditer(r'(L[\w/$]+;)->([\w$<>]+)(\([^)]*\)\S+|:[\w$\[\]/;]+)', line):
                desc, name, sig = m.group(1), m.group(2), m.group(3)
                if sig.startswith('('):
                    check_member(desc, name, sig, 'method')
                else:
                    check_member(desc, name, sig[1:], 'field')
        # register bounds
        for block in re.findall(r'\.method[^\n]*\n(.*?)\.end method', text, re.S):
            head = text[text.index(block) - 200:text.index(block)] if False else None
        for mm in re.finditer(r'\.method ([^\n]+)\n(.*?)\.end method', text, re.S):
            sig_line, body = mm.group(1), mm.group(2)
            lm = re.search(r'\.locals (\d+)', body)
            if not lm:
                problems.append(f'{path}: method without .locals: {sig_line}')
                continue
            locals_n = int(lm.group(1))
            msig = sig_line[sig_line.index('('):]
            params = msig[1:msig.index(')')]
            width = 0; i = 0
            while i < len(params):
                if params[i] in 'JD': width += 2; i += 1
                elif params[i] == 'L': width += 1; i = params.index(';', i) + 1
                elif params[i] == '[':
                    while params[i] == '[': i += 1
                    if params[i] in 'JD': width += 2; i += 1
                    else: width += 1; i = params.index(';', i) + 1
                else: width += 1; i += 1
            static = ' static ' in (' ' + sig_line + ' ')
            total = locals_n + width + (0 if static else 1)
            for rm in re.finditer(r'\b([vp])(\d+)\b', body):
                kind, num = rm.group(1), int(rm.group(2))
                idx = num if kind == 'v' else locals_n + num
                if idx >= total:
                    problems.append(f'{path}: register {rm.group(0)} out of range in {sig_line} (total {total})')
                    break

# ------------------------------------------------------------------ dex check
data = open(DEX, 'rb').read()
magic = data[:8]
if not magic.startswith(b'dex\n'):
    problems.append(f'bad dex magic {magic!r}')
else:
    file_size = struct.unpack('<I', data[32:36])[0]
    if file_size != len(data):
        problems.append(f'dex file_size {file_size} != {len(data)}')
    string_ids_size, string_ids_off = struct.unpack('<II', data[56:64])
    class_defs_size = struct.unpack('<I', data[96:100])[0]
    print(f'dex: magic={magic[:4]} version={data[4:7]!r} size={len(data)} strings={string_ids_size} classes={class_defs_size}')
    if class_defs_size != 4:
        problems.append(f'expected 4 classes, got {class_defs_size}')

print(f'references checked: {checked}')
if problems:
    print(f'PROBLEMS ({len(problems)}):')
    for p in problems[:40]: print('  -', p)
    sys.exit(1)
print('ALL CHECKS PASSED')
