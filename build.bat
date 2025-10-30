@echo off
echo ================================================================================
echo Компіляція PrintTo Address Matcher в EXE
echo ================================================================================
echo.

echo [1/4] Очищення старих збірок...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo Готово!
echo.

echo [2/4] Запуск PyInstaller...
pyinstaller build_exe.spec --clean
echo Готово!
echo.

echo [3/4] Створення структури директорій...
if not exist dist\PrintToAddressMatcher\cache mkdir dist\PrintToAddressMatcher\cache
if not exist dist\PrintToAddressMatcher\logs mkdir dist\PrintToAddressMatcher\logs
echo Готово!
echo.

echo [4/4] Готово!
echo.
echo ================================================================================
echo EXE файл знаходиться тут:
echo dist\PrintToAddressMatcher.exe
echo.
echo Структура:
echo dist\
echo   PrintToAddressMatcher.exe  - головний файл
echo   cache\                      - кеш (створюється автоматично)
echo   logs\                       - логи (створюється автоматично)
echo ================================================================================
echo.
pause