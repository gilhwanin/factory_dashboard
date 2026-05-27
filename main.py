import sys
from PyQt5.QtWidgets import QApplication
from ci_cd.updatedown import check_version_and_update
from core.widget import OrderDashboardWidget

CURRENT_VERSION = "a-0038"
PROGRAM_NAME = "factory_dashboard"

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        check_version_and_update(PROGRAM_NAME, CURRENT_VERSION)

        w = OrderDashboardWidget()

        screen = app.primaryScreen().availableGeometry()
        w.resize(screen.width(), screen.height())

        w.show()
        sys.exit(app.exec_())

    except Exception:
        import traceback
        print("\n===== 실행 중 오류 발생 =====")
        print(traceback.format_exc())
        input("\n 엔터를 누르면 닫힙니다...")
