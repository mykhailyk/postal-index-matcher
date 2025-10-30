import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt5.QtCore import Qt
from ui.main_window import MainWindow
from utils.logger import Logger
import config


class LoadingSplash(QWidget):
    """Splash screen"""
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFixedSize(450, 200)
        
        # Центруємо
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #34495e, stop:1 #2c3e50);
                border-radius: 10px;
                border: 2px solid #3498db;
            }
        """)
        
        title = QLabel("Print to Address Matcher v2.1")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold; background: transparent;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        self.status_label = QLabel("Завантаження...")
        self.status_label.setStyleSheet("color: #ecf0f1; font-size: 14px; background: transparent;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.progress = QProgressBar()
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #34495e;
                border-radius: 5px;
                text-align: center;
                color: white;
                background-color: #2c3e50;
            }
            QProgressBar::chunk {
                background: #3498db;
            }
        """)
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        layout.addWidget(self.progress)
        
        self.details = QLabel("")
        self.details.setStyleSheet("color: #95a5a6; font-size: 10px; background: transparent;")
        self.details.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.details)
        
        self.setLayout(layout)
    
    def update(self, message, progress, details=""):
        self.status_label.setText(message)
        self.progress.setValue(progress)
        self.details.setText(details)
        QApplication.processEvents()


def main():
    """Точка входу з splash screen"""
    logger = Logger()
    logger.info("=" * 80)
    logger.info("Запуск програми Address Matcher v2.1")
    logger.info("=" * 80)
    
    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        
        # Показуємо splash
        splash = LoadingSplash()
        splash.show()
        splash.update("Ініціалізація...", 10)
        
        # Завантажуємо пошуковий движок
        splash.update("Завантаження бази даних...", 30, "Magistral.csv (330K записів)")
        from search.hybrid_search import HybridSearch
        search_engine = HybridSearch()
        
        splash.update("База завантажена!", 60, f"{len(search_engine.magistral_records):,} записів")
        
        # Будуємо індекс Укрпошти (ЯКЩО потрібно)
        splash.update("Підготовка довідника...", 70, "Побудова індексу міст")
        from utils.ukrposhta_index import UkrposhtaIndex
        ukr_index = UkrposhtaIndex()
        if not ukr_index.load():
            splash.update("Побудова індексу Укрпошти...", 75, "Це займе ~2 хв")
            ukr_index.build(search_engine.magistral_records)
        
        splash.update("Індекс готовий!", 85)
        
        # Створюємо вікно
        splash.update("Створення інтерфейсу...", 90)
        window = MainWindow()
        
        # Передаємо УЖЕ ГОТОВИЙ індекс
        window.address_panel.ukr_index = ukr_index
        window.address_panel.magistral_cache = search_engine.magistral_records
        
        splash.update("Готово!", 100)
        import time
        time.sleep(0.2)
        
        splash.close()
        window.show()
        
        logger.info("Програма успішно запущена")
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.critical(f"Критична помилка: {e}")
        raise


if __name__ == '__main__':
    main()
