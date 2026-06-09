import csv
import io
from typing import List, Optional


def is_answer_cell(cell: str) -> bool:
    c = cell.strip().upper()
    return (c.isdigit() and 1 <= int(c) <= 9) or (len(c) == 1 and 'A' <= c <= 'D')


def detect_delimiter(line: str) -> Optional[str]:
    if '\t' in line:
        return '\t'
    if '|' in line:
        return '|'
    if ',' in line:
        return ','
    return None


def split_row(line: str, delimiter: str) -> List[str]:
    if delimiter == '|':
        return [c.strip() for c in line.split('|')]
    reader = csv.reader(io.StringIO(line), delimiter=delimiter)
    return [c.strip() for c in next(reader, [])]


def parse_csv_quiz(text: str) -> Optional[List[dict]]:
    """
    Parse pipe or tab separated quiz text.
    Format: Question | A | B | C | D | 2   (pipe)
            Question\tA\tB\tC\tD\t2        (tab)
    Last column is always the answer (1-4 or A-D).
    """
    text_clean = text.strip()
    if not text_clean:
        return None

    lines = [l for l in text_clean.split('\n') if l.strip()]
    if not lines:
        return None

    delimiter = detect_delimiter(lines[0])
    if not delimiter:
        return None

    rows = []
    for line in lines:
        row = split_row(line, delimiter)
        if any(c for c in row):
            rows.append(row)

    if not rows:
        return None

    header_lower = lines[0].lower()
    quiz_keywords = ["question", "option", "answer", "उत्तर", "प्रश्न", "विकल्प", "code"]
    has_header = any(kw in header_lower for kw in quiz_keywords)

    data_rows = rows[1:] if has_header else rows
    if not data_rows:
        return None

    # Validate that last column looks like an answer
    if not is_answer_cell(data_rows[0][-1]):
        return None

    questions = []
    for row in data_rows:
        if len(row) < 3:
            continue

        question = row[0]
        options  = [o for o in row[1:-1] if o]
        ans_raw  = row[-1].upper()

        if not question or not options:
            continue

        correct_option_id = 0
        if ans_raw.isdigit():
            correct_option_id = max(0, int(ans_raw) - 1)
        elif len(ans_raw) == 1 and ans_raw.isalpha():
            correct_option_id = ord(ans_raw) - ord('A')

        correct_option_id = min(correct_option_id, len(options) - 1)

        questions.append({
            "question":          question,
            "options":           options,
            "correct_option_id": correct_option_id,
            "explanation":       f"✅ सही उत्तर: {options[correct_option_id]}",
        })

    return questions if questions else None
