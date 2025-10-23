"""
Менеджер налаштувань програми
"""
import json
import os
import config


class SettingsManager:
    """Менеджер для збереження/завантаження налаштувань"""
    
    @staticmethod
    def load_settings():
        """Завантажує налаштування"""
        if not os.path.exists(config.SETTINGS_FILE):
            return {}
        
        try:
            with open(config.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    @staticmethod
    def save_settings(settings):
        """Зберігає налаштування"""
        try:
            with open(config.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Помилка збереження налаштувань: {e}")
    
    @staticmethod
    def get_last_file_path():
        """Повертає останній відкритий файл"""
        settings = SettingsManager.load_settings()
        return settings.get('last_file_path', '')
    
    @staticmethod
    def set_last_file_path(file_path):
        """Зберігає останній відкритий файл"""
        settings = SettingsManager.load_settings()
        settings['last_file_path'] = file_path
        SettingsManager.save_settings(settings)

    @staticmethod
    def get_window_geometry():
        """Повертає розмір та позицію вікна"""
        settings = SettingsManager.load_settings()
        return settings.get('window_geometry', {})

    @staticmethod
    def set_window_geometry(x, y, width, height):
        """Зберігає розмір вікна"""
        settings = SettingsManager.load_settings()
        settings['window_geometry'] = {'x': x, 'y': y, 'width': width, 'height': height}
        SettingsManager.save_settings(settings)

    @staticmethod
    def get_column_widths():
        """Повертає ширини стовпців"""
        settings = SettingsManager.load_settings()
        return settings.get('column_widths', [])

    @staticmethod
    def set_column_widths(widths):
        """Зберігає ширини стовпців"""
        settings = SettingsManager.load_settings()
        settings['column_widths'] = widths
        SettingsManager.save_settings(settings)

    @staticmethod
    def get_splitter_sizes(splitter_name):
        """Повертає розміри splitter"""
        settings = SettingsManager.load_settings()
        return settings.get(f'splitter_{splitter_name}', [])

    @staticmethod
    def set_splitter_sizes(splitter_name, sizes):
        """Зберігає розміри splitter"""
        settings = SettingsManager.load_settings()
        settings[f'splitter_{splitter_name}'] = sizes
        SettingsManager.save_settings(settings)
