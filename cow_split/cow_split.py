import sys
import os
import fitz  # PyMuPDF
from PIL import Image
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QFileDialog,
    QMessageBox, QLineEdit, QLabel
)


class PDFSplitter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('PDF to JPG 분할기')
        self.setGeometry(300, 300, 420, 470)

        # PDF 선택
        self.btn = QPushButton('PDF 파일 선택', self)
        self.btn.setGeometry(50, 30, 320, 50)
        self.btn.clicked.connect(self.select_pdf)

        # 날짜 입력
        self.label_date = QLabel('날짜 (YYYYMMDD):', self)
        self.label_date.setGeometry(50, 100, 200, 25)

        self.date_input = QLineEdit(self)
        self.date_input.setGeometry(50, 125, 320, 30)
        self.date_input.setPlaceholderText('예: 20251225')

        # 이미지 분할
        self.btn_split = QPushButton('이미지 분할 실행', self)
        self.btn_split.setGeometry(50, 165, 320, 45)
        self.btn_split.clicked.connect(self.split_images)

        # 파일 키 입력
        self.label_key = QLabel('파일명 키 입력:', self)
        self.label_key.setGeometry(50, 220, 200, 25)

        self.key_input = QLineEdit(self)
        self.key_input.setGeometry(50, 245, 320, 30)
        self.key_input.setPlaceholderText('예: 1 또는 2')

        # A 회전
        self.btn_rotate_a = QPushButton('A 뒤집기 (180°)', self)
        self.btn_rotate_a.setGeometry(50, 285, 150, 45)
        self.btn_rotate_a.clicked.connect(lambda: self.rotate_images('A'))

        # B 회전
        self.btn_rotate_b = QPushButton('B 뒤집기 (180°)', self)
        self.btn_rotate_b.setGeometry(220, 285, 150, 45)
        self.btn_rotate_b.clicked.connect(lambda: self.rotate_images('B'))

        # A ↔ B 파일명 교체
        self.btn_swap = QPushButton('A ↔ B 파일명 SWAP', self)
        self.btn_swap.setGeometry(50, 340, 320, 45)
        self.btn_swap.clicked.connect(self.swap_ab_files)

        # '_' 제거 버튼
        self.btn_remove_underscore = QPushButton("output 폴더 '_' 제거", self)
        self.btn_remove_underscore.setGeometry(50, 395, 320, 45)
        self.btn_remove_underscore.clicked.connect(self.remove_underscores)

    # ---------------- PDF → JPG ----------------

    def select_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'PDF 파일 선택', '', 'PDF Files (*.pdf)'
        )
        if file_path:
            self.convert_pdf_to_images(file_path)

    def convert_pdf_to_images(self, pdf_path):
        try:
            output_dir = r'C:\gyunwoo\image\processed'
            os.makedirs(output_dir, exist_ok=True)

            doc = fitz.open(pdf_path)
            img_index = 1

            for page in doc:
                pix = page.get_pixmap(dpi=300)

                page_num = (img_index + 1) // 2
                suffix = 'A' if img_index % 2 == 1 else 'B'

                filename = f'{page_num}{suffix}.jpg'
                pix.save(os.path.join(output_dir, filename))
                img_index += 1

            QMessageBox.information(
                self, '완료',
                f'{img_index-1}개 페이지 JPG 변환 완료\n{output_dir}'
            )

        except Exception as e:
            QMessageBox.critical(self, '오류', f'변환 오류:\n{str(e)}')

    # ---------------- 이미지 좌우 분할 ----------------

    def split_images(self):
        date_value = self.date_input.text().strip()
        if not date_value:
            QMessageBox.warning(self, '경고', '날짜를 입력하세요.')
            return

        INPUT_DIR = rf"C:\gyunwoo\image\{date_value}jp"
        OUTPUT_DIR = os.path.join(INPUT_DIR, "output")

        if not os.path.exists(INPUT_DIR):
            QMessageBox.warning(self, '경고', f'폴더 없음:\n{INPUT_DIR}')
            return

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        VALID_EXT = (".jpg", ".jpeg", ".png")

        try:
            count = 0
            for filename in os.listdir(INPUT_DIR):
                if not filename.lower().endswith(VALID_EXT):
                    continue

                img = Image.open(os.path.join(INPUT_DIR, filename))
                w, h = img.size
                mid = w // 2

                left = img.crop((0, 0, mid, h))
                right = img.crop((mid, 0, w, h))

                name, ext = os.path.splitext(filename)
                left.save(os.path.join(OUTPUT_DIR, f"{name}A{ext}"))
                right.save(os.path.join(OUTPUT_DIR, f"{name}B{ext}"))
                count += 1

            QMessageBox.information(self, '완료', f'{count}개 분할 완료')

        except Exception as e:
            QMessageBox.critical(self, '오류', f'분할 오류:\n{str(e)}')

    # ---------------- A/B 회전 ----------------

    def rotate_images(self, suffix):
        date_value = self.date_input.text().strip()
        key_value = self.key_input.text().strip()

        if not date_value or not key_value:
            QMessageBox.warning(self, '경고', '날짜와 파일키 입력 필요')
            return

        TARGET_DIR = rf"C:\gyunwoo\image\{date_value}jp\output"
        if not os.path.exists(TARGET_DIR):
            QMessageBox.warning(self, '경고', 'output 폴더 없음')
            return

        VALID_EXT = (".jpg", ".jpeg", ".png")
        count = 0

        try:
            target_name = f"{key_value}{suffix}"

            for filename in os.listdir(TARGET_DIR):
                if not filename.lower().endswith(VALID_EXT):
                    continue
                if os.path.splitext(filename)[0] != target_name:
                    continue

                path = os.path.join(TARGET_DIR, filename)
                img = Image.open(path)
                img.rotate(180, expand=True).save(path)
                count += 1

            QMessageBox.information(self, '완료', f'{count}개 회전 완료')

        except Exception as e:
            QMessageBox.critical(self, '오류', f'회전 오류:\n{str(e)}')

    # ---------------- A ↔ B 파일명 SWAP ----------------

    def swap_ab_files(self):
        date_value = self.date_input.text().strip()
        key_value = self.key_input.text().strip()

        if not date_value or not key_value:
            QMessageBox.warning(self, '경고', '날짜와 파일키 입력 필요')
            return

        TARGET_DIR = rf"C:\gyunwoo\image\{date_value}jp\output"

        file_a = os.path.join(TARGET_DIR, f"{key_value}A.jpg")
        file_b = os.path.join(TARGET_DIR, f"{key_value}B.jpg")

        if not os.path.exists(file_a) or not os.path.exists(file_b):
            QMessageBox.critical(
                self, '오류',
                f"A 또는 B 파일이 존재하지 않습니다.\n\n{file_a}\n{file_b}"
            )
            return

        try:
            temp = os.path.join(TARGET_DIR, f"{key_value}_TMP.jpg")
            if os.path.exists(temp):
                os.remove(temp)

            os.rename(file_a, temp)
            os.rename(file_b, file_a)
            os.rename(temp, file_b)

            QMessageBox.information(self, '완료', 'A ↔ B 파일명 교체 완료')

        except Exception as e:
            QMessageBox.critical(self, '오류', f'SWAP 오류:\n{str(e)}')

    # ---------------- output 폴더 '_' 제거 ----------------

    def remove_underscores(self):
        date_value = self.date_input.text().strip()
        if not date_value:
            QMessageBox.warning(self, '경고', '날짜 입력 필요')
            return

        TARGET_DIR = rf"C:\gyunwoo\image\{date_value}jp\output"
        if not os.path.exists(TARGET_DIR):
            QMessageBox.warning(self, '경고', 'output 폴더 없음')
            return

        VALID_EXT = (".jpg", ".jpeg", ".png")
        renamed = 0

        try:
            for filename in os.listdir(TARGET_DIR):
                if not filename.lower().endswith(VALID_EXT):
                    continue
                if "_" not in filename:
                    continue

                new_name = filename.replace("_", "")
                os.rename(
                    os.path.join(TARGET_DIR, filename),
                    os.path.join(TARGET_DIR, new_name)
                )
                renamed += 1

            QMessageBox.information(self, '완료', f'{renamed}개 파일 언더바 제거 완료')

        except Exception as e:
            QMessageBox.critical(self, '오류', f'언더바 제거 오류:\n{str(e)}')


# ---------------- 실행 ----------------

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PDFSplitter()
    window.show()
    sys.exit(app.exec_())
