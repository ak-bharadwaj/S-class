const fs = require('fs');
const crypto = require('crypto');
const vectors = JSON.parse(fs.readFileSync(__dirname + '/c1-vectors.v6.0.1.json', 'utf8'));
function canonicalObject(name) {
  switch (name) {
    case 'enum': return {'$enum':'ActionType','$name':'CODE_EDIT'};
    case 'bytes': return {'$bytes':Buffer.from([0,255]).toString('base64')};
    case 'tuple': return ['a',1,true];
    case 'set': return {'$set':['a','z']};
    case 'null': return null;
    case 'bool': return false;
    case 'int_zero': return 0;
    case 'int_max': return 9223372036854775807n;
    case 'int_min': return -9223372036854775808n;
    case 'nfc_string': return 'é';
    case 'nested': return ['x',[1,2],{'$set':[3,4]}];
    case 'map': return {'$map':[['a',1],[2,'b']]};
    default: throw new Error('unknown vector '+name);
  }
}
function stable(v) {
  if (Array.isArray(v)) return v.map(stable);
  if (v && typeof v === 'object' && !Buffer.isBuffer(v)) {
    const o={}; for (const k of Object.keys(v).sort()) o[k]=stable(v[k]); return o;
  }
  return v;
}
function encode(v) {
  if (typeof v === 'bigint') return v.toString();
  if (typeof v === 'string') return JSON.stringify(v);
  if (v === null) return 'null';
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'number') return JSON.stringify(v);
  if (Array.isArray(v)) return '['+v.map(encode).join(',')+']';
  if (v && typeof v === 'object') return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+encode(v[k])).join(',')+'}';
  throw new Error('unsupported');
}
function c1(v) { return Buffer.from(encode(stable(v))); }
function digest(v) {
  return 'sha256:' + crypto.createHash('sha256').update(Buffer.concat([Buffer.from(vectors.domain,'utf8'),Buffer.from([0]),c1(v)])).digest('hex');
}
for (const row of vectors.vectors) {
  const bytes=c1(canonicalObject(row.name));
  const b64=bytes.toString('base64');
  if (b64 !== row.canonical_c1_base64) throw new Error(row.name+': canonical bytes mismatch');
  if (digest(canonicalObject(row.name)) !== row.digest) throw new Error(row.name+': digest mismatch');
}
console.log(`C1_INDEPENDENT_JS_OK ${vectors.vectors.length}`);
