# 🛡️ NFC Windows Guard (ACR122U)

> **Аппаратная аутентификация по смарт-карте NFC (ACS ACR122U) и паролю Windows с дизайном Apple (SF Pro Display).**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Hardware](https://img.shields.io/badge/Hardware-ACR122U%20NFC-brightgreen.svg)](https://www.acs.com.hk/en/products/3/acr122u-usb-nfc-smart-card-reader/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078d4.svg)](https://www.microsoft.com/windows/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📖 Описание проекта

**NFC Windows Guard** — специализированный комплекс безопасности для Windows, интегрирующий считыватель **ACS ACR122U** в качестве удобного и быстрого физического ключа разблокировки системы наряду со штатным паролем.

При запуске компьютера, ручной блокировке (`Win + L` или `Ctrl + Alt + L`) экран на **всех мониторах** блокируется стильным экраном в эстетике **Apple macOS / iOS 18**.

### 🔓 Два полноценных способа разблокировки системы прямо на экране:

1. **Аппаратный способ (Ключ-карта NFC)**:
   * Приложите карту или брелок к считывателю ACR122U.
   * Система считывает UID карты, сверяет с белым списком, подает приятный звуковой сигнал и мгновенно разблокирует компьютер!
   * Предусмотрено **3 попытки** прикладывания карты. При исчерпании попыток ридер блокируется, требуя ввода пароля.
2. **Штатный способ (Пароль или PIN Windows)**:
   * Прямо на экране блокировки доступно поле ввода пароля.
   * Введите ваш стандартный пароль учетной записи Windows (или заданный мастер-PIN) и нажмите `Enter` (или кнопку `➔`).
   * **Система мгновенно разблокируется и больше НЕ запрашивает карту!**

---

## 🖥️ Интерфейс Apple Human Interface

* 🍎 **Оригинальный шрифт Apple SF Pro Display**:
  * Встроенные начертания *SF Pro Display* (Light, Regular, Medium, Bold).
  * Крупные часы и аккуратная локализованная дата.
* 💳 **Векторная графика Apple Contactless**:
  * Фирменные 4 дуги бесконтактной оплаты без использования смайликов и эмодзи.
  * Точечные индикаторы попыток в стиле парольных капсул macOS.
* 🎨 **Благородные темы оформления**:
  * *Apple Dark (Тёмная macOS)*
  * *Apple Space Gray (Титан)*
  * *Apple Midnight (Полночь)*
  * *Apple Forest (Альпийская зелень)*
  * *Apple Crimson (Глубокий рубин)*
  * *Apple Light (Светлое серебро)*
* 🖥️ **Поддержка нескольких мониторов**:
  * Все экраны перекрываются защитными оверлеями в едином стиле.

---

## 🚀 Настройка вызова по Win + L

По умолчанию Windows обрабатывает нажатие `Win + L` на уровне ядра, переводя пользователя на стандартный экран блокировки Windows.

Чтобы нажатие **`Win + L`** сразу открывало экран **NFC Guard**:
1. Запустите файл [enable_win_l_interception.bat](enable_win_l_interception.bat) (или нажмите кнопку *«🔒 Настроить перехват Win+L»* в разделе *«Служба и Win+L»*).
2. Подтвердите запрос прав администратора (UAC).
3. Теперь при нажатии `Win + L` поверх рабочего стола сразу появится экран авторизации NFC Guard!
*(Для возврата стандартного поведения запустите `disable_win_l_interception.bat`).*

> **Совет**: В любой момент также работает альтернативное быстрое сочетание клавиш **`Ctrl + Alt + L`** (работает без необходимости включения политик реестра).

---

## ⚙️ Установка и Быстрый старт

### 1. Установка зависимостей
Запустите `setup_environment.bat` или выполните:
```bash
pip install -r requirements.txt
```

### 2. Добавление карты
Запустите [open_settings.bat](open_settings.bat):
1. Перейдите во вкладку **«💳 Ключ-карты»**.
2. Нажмите **«Сканировать с ридера»** и приложите карту к ACR122U.
3. Введите название и нажмите **«+ Добавить»**.

### 3. Запуск фоновой службы
1. В настройках во вкладке **«⚡ Служба и Win+L»** нажмите **«Запустить службу»** (или запустите [start_daemon.bat](start_daemon.bat)).
2. Включите **«Автозапуск службы при старте Windows»** (или запустите [install_autostart.bat](install_autostart.bat)).

---

## 📁 Структура проекта

```text
nfc-windows-guard/
├── assets/fonts/             # Шрифты Apple SF Pro Display
├── nfc_guard/
│   ├── config.py             # Настройки, темы и белый список
│   ├── daemon.py             # Фоновая служба в трее (Win+L, сессии)
│   ├── fonts.py              # Менеджер шрифтов SF Pro
│   ├── hooks.py              # Низкоуровневые хуки клавиатуры
│   ├── icons.py              # Векторные глифы Apple Contactless
│   ├── lock_screen.py        # Экран блокировки (NFC + Пароль)
│   ├── reader.py             # Драйвер ACR122U (APDU, зуммер, LED)
│   ├── settings_window.py    # Панель управления macOS System Settings
│   └── utils.py              # Аутентификация Windows LogonUserW
├── enable_win_l_interception.bat   # Включение перехвата Win+L
├── disable_win_l_interception.bat  # Отключение перехвата Win+L
├── start_daemon.bat          # Запуск службы в трее
├── start_lock.bat            # Тест экрана блокировки
├── open_settings.bat         # Открытие настроек
├── install_autostart.bat     # Добавление в автозагрузку Windows
├── requirements.txt          # Зависимости
└── README.md
```

---

## 📄 Лицензия

MIT License (c) 2026 procuroroff
