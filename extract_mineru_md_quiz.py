import json
import re
import shutil
from pathlib import Path


Q_ID = "3e04ee63-84a2-46b9-af0d-0f9a9d0395d0"
A_ID = "defffd63-ccd8-4de4-b263-00eac46190d8"
ROOT = Path.home() / "MinerU"
OUT_DIR = Path(__file__).resolve().parent / "天然药物化学"
OUT_IMAGES = OUT_DIR / "images"
IMG_RE = re.compile(r"!\[\]\((images/[^)]+)\)")
NUM_RE = re.compile(r"^(\d{1,3})[.．、](?!\d)\s*(.*)$")
ANSWER_PAIR_RE = re.compile(r"(\d{1,3})[.．、]\s*([A-E]{1,5}|[√×]|正确|错误)")


def source_dir(suffix: str) -> Path:
    matches = list(ROOT.glob(f"*{suffix}"))
    if not matches:
        raise FileNotFoundError(suffix)
    return matches[0]


Q_DIR = source_dir(Q_ID)
A_DIR = source_dir(A_ID)


def read_lines(path: Path):
    return path.read_text(encoding="utf-8").splitlines()


def clean(text: str) -> str:
    text = re.sub(r"\\_", "_", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def heading_text(line: str) -> str:
    return clean(re.sub(r"^#+\s*", "", line))


def is_heading(line: str) -> bool:
    return line.lstrip().startswith("#")


def is_context(text: str) -> bool:
    return bool(re.match(r"第[一二三四五六七八九十]+章", text) or re.match(r"综合练习[一二三四五六七八九十]+", text))


def context_key(text: str) -> str:
    match = re.match(r"(第[一二三四五六七八九十]+章)", text)
    if match:
        return match.group(1)
    match = re.match(r"(综合练习[一二三四五六七八九十]+)", text)
    if match:
        return match.group(1)
    return text


def section_type(section: str) -> str:
    if "判断题" in section:
        return "判断题"
    if "选择题" in section or "单项选择题" in section or "多项选择题" in section or "多选题" in section:
        return "选择题"
    if "填空题" in section:
        return "填空题"
    return "问答题"


def qtype_from_section(section: str, answer: str = "") -> str:
    if "判断题" in section:
        return "判断题"
    if "选择题" in section or "单项选择题" in section or "多项" in section or "多选" in section:
        if "多项" in section or "多选" in section or len(re.sub(r"[^A-E]", "", answer or "")) > 1:
            return "多选题"
        return "单选题"
    if "填空题" in section:
        return "填空题"
    return "问答题"


def copy_image(rel: str, src_dir: Path) -> str:
    OUT_IMAGES.mkdir(parents=True, exist_ok=True)
    name = Path(rel).name
    src = src_dir / rel
    dst = OUT_IMAGES / name
    if src.exists() and not dst.exists():
        shutil.copy2(src, dst)
    return f"images/{name}"


def extract_images(text: str, src_dir: Path):
    imgs = [copy_image(match, src_dir) for match in IMG_RE.findall(text)]
    return clean(IMG_RE.sub("", text)), imgs


def option_line(line: str):
    m = re.match(r"^([A-E])\s*[.．、]\s*(.*)$", line.strip())
    if m:
        return m.group(1), m.group(2)
    return None


def split_inline_options(text: str):
    matches = list(re.finditer(r"(?<![A-Za-z])([A-E])\s*[.．、]\s*", text))
    if len(matches) < 2:
        return None
    stem = clean(text[: matches[0].start()])
    opts = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        opts.append((m.group(1), clean(text[m.end() : end])))
    return stem, opts


def parse_questions():
    lines = read_lines(Q_DIR / "full.md")
    questions = []
    context = ""
    section = ""
    in_questions = False
    current = None

    def finish_choice():
        nonlocal current
        if not current:
            return
        options = [item["text"] or "见图片" for item in current["options"]]
        option_images = {item["letter"]: item["images"] for item in current["options"] if item["images"]}
        questions.append({
            "题型": qtype_from_section(section),
            "题干": f"{context}｜{section}｜第{current['no']}题\n{clean(current['stem'])}",
            "选项": options,
            "答案": "",
            "解析": "",
            "题干图片": current["images"],
            "选项图片": option_images,
            "答案图片": [],
            "_key": (context_key(context), section, current["no"]),
        })
        current = None

    i = 0
    while i < len(lines):
        raw = lines[i].strip()
        i += 1
        if not raw:
            continue
        text, imgs = extract_images(raw, Q_DIR)
        if is_heading(raw):
            h = heading_text(raw)
            if is_context(h):
                context = h
                in_questions = context.startswith("综合练习")
            elif h == "【知识与能力测评】":
                in_questions = True
            elif in_questions and re.match(r"^[一二三四五六七八九十]+、", h):
                finish_choice()
                section = h
            continue
        if not in_questions or not context or not section:
            continue

        stype = section_type(section)
        if stype == "选择题":
            opt = option_line(text)
            if opt and current:
                letter, body = opt
                current["options"].append({"letter": letter, "text": body, "images": imgs})
                continue
            m = NUM_RE.match(text)
            if m:
                finish_choice()
                no, body = m.groups()
                inline = split_inline_options(body)
                if inline:
                    stem, opts = inline
                    current = {"no": no, "stem": stem, "images": imgs, "options": []}
                    for letter, opt_text in opts:
                        current["options"].append({"letter": letter, "text": opt_text, "images": []})
                else:
                    current = {"no": no, "stem": body, "images": imgs, "options": []}
                continue
            if current:
                if imgs and current["options"]:
                    current["options"][-1]["images"].extend(imgs)
                elif imgs:
                    current["images"].extend(imgs)
                elif current["options"]:
                    current["options"][-1]["text"] = clean(current["options"][-1]["text"] + " " + text)
                else:
                    current["stem"] = clean(current["stem"] + " " + text)
            continue

        finish_choice()
        numbered_items = [] if stype == "问答题" else split_numbered_questions(text)
        if numbered_items:
            for no, body in numbered_items:
                questions.append({
                    "题型": "判断题" if stype == "判断题" else ("填空题" if stype == "填空题" else "问答题"),
                    "题干": f"{context}｜{section}｜第{no}题\n{body}",
                    "选项": [],
                    "答案": "",
                    "解析": "",
                    "题干图片": imgs if no == numbered_items[0][0] else [],
                    "选项图片": {},
                    "答案图片": [],
                    "_key": (context_key(context), section, no),
                })
        else:
            m = NUM_RE.match(text)
            if m:
                no, body = m.groups()
                questions.append({
                    "题型": "判断题" if stype == "判断题" else ("填空题" if stype == "填空题" else "问答题"),
                    "题干": f"{context}｜{section}｜第{no}题\n{body}",
                    "选项": [],
                    "答案": "",
                    "解析": "",
                    "题干图片": imgs,
                    "选项图片": {},
                    "答案图片": [],
                    "_key": (context_key(context), section, no),
                })
            elif questions:
                if text:
                    questions[-1]["题干"] = clean(questions[-1]["题干"] + " " + text)
                if imgs:
                    questions[-1]["题干图片"].extend(imgs)
    finish_choice()
    return questions


def answer_pairs(text: str):
    out = {}
    for m in ANSWER_PAIR_RE.finditer(text):
        ans = m.group(2)
        if ans == "√":
            ans = "正确"
        elif ans == "×":
            ans = "错误"
        out[m.group(1)] = ans
    return out


def split_numbered_answers(text: str, max_len: int | None = None):
    items = {}
    matches = list(re.finditer(r"(?<![A-Za-z])(\d{1,3})[.．、](?!\d)\s*", text))
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = clean(text[start:end])
        if not body:
            continue
        if max_len is not None and len(body) > max_len:
            body = body[:max_len].rstrip() + "..."
        items[match.group(1)] = body
    return items


def split_numbered_answer_entries(entries, max_len: int | None = None):
    items = {}
    current_no = None
    current_texts = []
    current_imgs = []

    def commit():
        nonlocal current_no, current_texts, current_imgs
        if not current_no:
            return
        body = clean(" ".join(current_texts))
        if max_len is not None and len(body) > max_len:
            body = body[:max_len].rstrip() + "..."
        if body or current_imgs:
            items[current_no] = {
                "答案": body or "见答案图片",
                "答案图片": current_imgs,
            }
        current_no = None
        current_texts = []
        current_imgs = []

    for text, imgs in entries:
        matches = list(re.finditer(r"(?<![A-Za-z])(\d{1,3})[.．、](?!\d)\s*", text))
        if not matches:
            if current_no:
                if text:
                    current_texts.append(text)
                if imgs:
                    current_imgs.extend(imgs)
            continue
        for idx, match in enumerate(matches):
            commit()
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            body = clean(text[start:end])
            current_no = match.group(1)
            current_texts = [body] if body else []
            current_imgs = imgs[:] if len(matches) == 1 or idx == 0 else []
    commit()
    return items


def split_numbered_questions(text: str):
    matches = list(re.finditer(r"(?<![A-Za-z])(\d{1,3})[.．、](?!\d)\s*", text))
    if not matches:
        return []
    items = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = clean(text[start:end])
        if body:
            items.append((match.group(1), body))
    return items


def parse_answers():
    lines = read_lines(A_DIR / "full.md")
    answers = {}
    context = ""
    section = ""
    buffer = []

    def flush():
        if not context or not section or not buffer:
            return
        text = clean(" ".join(item[0] for item in buffer))
        for no, ans in answer_pairs(text).items():
            answers[(context_key(context), section, no)] = {"答案": ans, "答案图片": []}
        stype = section_type(section)
        if text in {"略", "略。"}:
            answers[(context_key(context), section, "*")] = {"答案": "略。", "答案图片": []}
        if stype == "填空题":
            for no, answer_data in split_numbered_answer_entries(buffer, max_len=320).items():
                answers.setdefault((context_key(context), section, no), answer_data)
        elif stype == "问答题":
            for no, answer_data in split_numbered_answer_entries(buffer, max_len=1800).items():
                answers.setdefault((context_key(context), section, no), answer_data)
        buffer.clear()

    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        text, imgs = extract_images(raw, A_DIR)
        if is_heading(raw):
            h = heading_text(raw)
            if is_context(h):
                flush()
                context = h
                section = ""
            elif re.match(r"^[一二三四五六七八九十]+、", h):
                flush()
                section = h
            continue
        buffer.append((text, imgs))
    flush()
    return answers


def apply_answers(questions, answers):
    for q in questions:
        key = q.pop("_key")
        answer_data = answers.get(key, {"答案": "", "答案图片": []})
        if isinstance(answer_data, str):
            answer_data = {"答案": answer_data, "答案图片": []}
        if not answer_data["答案"]:
            answer_data = answers.get((key[0], key[1], "*"), {"答案": "", "答案图片": []})
            if isinstance(answer_data, str):
                answer_data = {"答案": answer_data, "答案图片": []}
        answer = answer_data["答案"]
        if not answer and section_type(key[1]) == "选择题":
            # Some answer headings use a shorter variant, e.g. "单项选择题" vs "选择题".
            for alt_section in ["一、选择题（每题只有一个最佳答案）", "四、单项选择题", "五、单项选择题", "三、选择题（每题只有一个最佳答案）"]:
                answer_data = answers.get((key[0], alt_section, key[2]), {"答案": "", "答案图片": []})
                if isinstance(answer_data, str):
                    answer_data = {"答案": answer_data, "答案图片": []}
                answer = answer_data["答案"]
                if answer:
                    break
        q["答案"] = answer
        q["答案图片"] = answer_data.get("答案图片", [])
        q["题型"] = qtype_from_section(key[1], answer)
        if q["题型"] == "问答题" and not q["答案"]:
            q["答案"] = "原书答案未识别为可编辑文字，可能为结构式图片、表格或原答案略。请结合题目图片或原书答案页核对。"
    return questions


def main():
    OUT_DIR.mkdir(exist_ok=True)
    OUT_IMAGES.mkdir(parents=True, exist_ok=True)
    questions = parse_questions()
    answers = parse_answers()
    questions = apply_answers(questions, answers)
    out = OUT_DIR / "题库.json"
    out.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
    stats = {}
    answered = 0
    for q in questions:
        stats[q["题型"]] = stats.get(q["题型"], 0) + 1
        answered += bool(q["答案"])
    print("输出:", out)
    print("题目数:", len(questions), stats)
    print("已匹配答案:", answered)
    print("选择/判断答案:", sum(bool(q["答案"]) for q in questions if q["题型"] in {"单选题", "多选题", "判断题"}), "/", sum(1 for q in questions if q["题型"] in {"单选题", "多选题", "判断题"}))
    print("图片数:", len(list(OUT_IMAGES.glob("*"))))


if __name__ == "__main__":
    main()
