/**
 * JSON parser chặt cho body request (spec v0.3 §4, từ điển schema "JSON Schema và cách dùng"):
 * từ chối key trùng và Unicode không hợp lệ (surrogate lẻ) trước validation và canonicalization.
 * `JSON.parse` lặng lẽ giữ key cuối và chấp nhận "\uD800", nên không dùng được cho mục đích này.
 * NaN/Infinity vốn không phải JSON nên tự bị từ chối.
 */

export class StrictJsonError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StrictJsonError";
  }
}

export function parseStrictJson(text: string): unknown {
  let i = 0;

  const error = (message: string): never => {
    throw new StrictJsonError(`${message} tại vị trí ${i}`);
  };
  const skip = () => {
    while (i < text.length && (text[i] === " " || text[i] === "\t" || text[i] === "\n" || text[i] === "\r")) i++;
  };
  const expect = (char: string) => {
    if (text[i] !== char) error(`Cần '${char}'`);
    i++;
  };

  const string = (): string => {
    const start = i;
    expect('"');
    while (i < text.length && text[i] !== '"') {
      const code = text.charCodeAt(i);
      if (code < 0x20) error("Ký tự điều khiển trong chuỗi");
      i += text[i] === "\\" ? (text[i + 1] === "u" ? 6 : 2) : 1;
    }
    expect('"');
    const value = JSON.parse(text.slice(start, i)) as string;
    if (!value.isWellFormed()) error("Unicode không hợp lệ");
    return value;
  };

  const value = (): unknown => {
    skip();
    const char = text[i];
    if (char === "{") {
      i++;
      const out: Record<string, unknown> = {};
      const seen = new Set<string>();
      skip();
      if (text[i] === "}") {
        i++;
        return out;
      }
      for (;;) {
        skip();
        const key = string();
        if (seen.has(key)) error("Key trùng");
        seen.add(key);
        skip();
        expect(":");
        // defineProperty để key "__proto__" là dữ liệu thường, không đổi prototype.
        Object.defineProperty(out, key, { value: value(), enumerable: true, writable: true, configurable: true });
        skip();
        if (text[i] === ",") {
          i++;
          continue;
        }
        expect("}");
        return out;
      }
    }
    if (char === "[") {
      i++;
      const out: unknown[] = [];
      skip();
      if (text[i] === "]") {
        i++;
        return out;
      }
      for (;;) {
        out.push(value());
        skip();
        if (text[i] === ",") {
          i++;
          continue;
        }
        expect("]");
        return out;
      }
    }
    if (char === '"') return string();
    const literal = text.slice(i).match(/^(?:true|false|null|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/);
    if (!literal) return error("Giá trị JSON không hợp lệ");
    i += literal[0].length;
    return JSON.parse(literal[0]);
  };

  if (!text.isWellFormed()) throw new StrictJsonError("Unicode không hợp lệ");
  const result = value();
  skip();
  if (i !== text.length) error("Dữ liệu thừa sau JSON");
  return result;
}
