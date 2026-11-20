"""GreenRoots Allotment Management System - run with:  python main.py"""
from services.application_service import ApplicationService
from ui.main_window import MainWindow


def main():
    app = ApplicationService()
    window = MainWindow(app)
    window.mainloop()


if __name__ == "__main__":
    main()
