import pytest

class DummySheet:
    def __init__(self):
        self.headers = []
        self.rows = []

    def row_values(self, row):
        if row == 1:
            return self.headers
        return self.rows[row-2] if row-2 < len(self.rows) else []

    def get_all_records(self):
        if not self.headers:
            return []
        return [dict(zip(self.headers, row)) for row in self.rows]

    def append_row(self, row, value_input_option=None):
        """데이터 행 추가 (헤더는 따로 지정해야 함)."""
        self.rows.append(row)

    def insert_row(self, row, index=1, value_input_option=None):
        """특정 위치에 행 삽입 (index=2 → 첫 데이터행)."""
        pos = max(0, index-2)
        self.rows.insert(pos, row)

    def delete_rows(self, row):
        """행 삭제 (row=2 → 첫 데이터행)."""
        if 0 <= row-2 < len(self.rows):
            self.rows.pop(row-2)


@pytest.fixture
def dummy_sheet():
    return DummySheet()
