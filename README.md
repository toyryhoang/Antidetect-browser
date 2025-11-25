# 🔒 Antidetect Browser - GoLogin Profile Manager

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Active-success.svg)

A powerful tool for managing and creating GoLogin browser profiles with advanced antidetect features for social media marketing automation.

## ✨ Key Features

- 🎭 **Automated Profile Creation**: Generate profiles with randomized fingerprints
- 🌐 **Proxy Integration**: Full support for HTTP/SOCKS proxies with authentication
- 🔐 **Canvas & WebGL Spoofing**: Advanced fingerprinting protection
- 📦 **Profile Compression**: Compress/decompress profiles to save storage
- 🚀 **Orbita Browser**: Compatible with Chromium-based Orbita engine
- 🎯 **WebRTC Protection**: Prevent WebRTC IP leaks
- 🖼️ **Client Rects Spoofing**: Protection against font fingerprinting
- 🎨 **Audio Context Noise**: Randomized audio fingerprints

## 📋 Requirements

```bash
Python 3.8+
selenium
requests
```

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/toyryhoang/Antidetect-browser.git
cd Antidetect-browser

# Install dependencies
pip install -r requirements.txt

# Download Orbita Browser (if not already installed)
python generator.py
```

## 💻 Usage

### Basic Profile Creation

```python
from create_profile import createProfile

# Create profile with auto-generated ID
profile_id = createProfile()
print(f"Profile created: {profile_id}")
```

### Create Profile with Proxy

```python
# Format: ip:port:username:password
proxy = "192.168.1.1:8080:user:pass"
profile_id = createProfile(proxy=proxy)
```

### Create Profile with Custom Name

```python
profile_id = createProfile(name="MyCustomProfile_001")
```

### Open Profile

```python
from open_profile import open_profile_with_selenium

# Open profile with Selenium
driver = open_profile_with_selenium(profile_id)

# Perform automation
driver.get("https://example.com")
# ... your automation code ...

driver.quit()
```

## 📁 Directory Structure

```
Antidetect-browser/
├── create_profile.py      # Create new profiles
├── open_profile.py        # Open and manage profiles
├── generator.py           # GoLogin core engine
├── fonts.json            # System fonts list
├── temp/                 # Profiles directory
│   ├── profile_id/       # Profile folder
│   └── profile_id.zip    # Compressed profile
└── .gologin/            # Orbita browser files
```

## ⚙️ Profile Configuration

```python
profile_config = {
    "version": "123.0.6312.59",  # Orbita version
    "os": "win",                  # win/mac/linux
    "canvas": {"mode": "noise"},  # Canvas fingerprint
    "webRTC": {"mode": "noise"},  # WebRTC protection
    "webGL": {"mode": "noise"},   # WebGL spoofing
    "audioContext": {"mode": True},
    "clientRects": {"mode": True},
    "geoLocation": {"mode": "noise"},
    "googleServicesEnabled": True,
    "doNotTrack": True
}
```

## 🎯 Use Cases

- 🔹 Social Media Marketing (SMM)
- 🔹 Multi-account management
- 🔹 Web scraping & automation
- 🔹 E-commerce automation
- 🔹 Ad verification
- 🔹 Privacy-focused browsing

## 🛠️ Technology Stack

- **Python**: Core language
- **Selenium WebDriver**: Browser automation
- **Orbita Browser**: Modified Chromium
- **GoLogin API**: Profile management

## 📊 Performance

- ⚡ Profile creation: ~5-10 seconds
- 💾 Profile size: ~50-100 MB (uncompressed)
- 🗜️ Compressed size: ~10-20 MB
- 🚀 Browser startup: ~3-5 seconds

## 🔧 Troubleshooting

### Profile creation failed
```bash
# Check if Orbita browser is installed correctly
ls .gologin/browser/orbita-browser-*/

# Clear cache and try again
rm -rf temp/*
```

### Proxy not working
```python
# Ensure correct format: ip:port:username:password
proxy = "123.45.67.89:8080:myuser:mypass"
```

## 🤝 Contributing

All contributions are welcome! Please:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 💖 Support the Project

If this project helps you, please consider donating to support development!

### 💰 Crypto Donations

<table>
  <tr>
    <td align="center">
      <img src="https://cryptologos.cc/logos/tether-usdt-logo.png" width="50"><br>
      <b>USDT (TRC20)</b><br>
      <code>TS6YyAdC9Q39yBVsbCAYYL9VLexrXQyJyg</code>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="https://cryptologos.cc/logos/bnb-bnb-logo.png" width="50"><br>
      <b>USDT (BEP20)</b><br>
      <code>0x46d604f05f627122d977406ff41d33a49e2d60e0</code>
    </td>
  </tr>
</table>

> ⚠️ **Important**: Double-check the network (TRC20/BEP20) before sending!

#### Why donate?
- 🔧 Maintain and update the project
- 🚀 Develop new features
- 📚 Write better documentation
- 🐛 Fix bugs and improve performance
- ☕ Buy coffee for the developer 😊

## 📝 License

This project is licensed under the [MIT License](LICENSE).

## ⚠️ Disclaimer

This tool is developed for educational purposes and legitimate automation. Users must comply with the Terms of Service of the platforms they use and local laws. The author is not responsible for misuse.

## 📞 Contact

- **GitHub**: [@toyryhoang](https://github.com/toyryhoang)
- **Project Link**: [https://github.com/toyryhoang/Antidetect-browser](https://github.com/toyryhoang/Antidetect-browser)

## 🌟 Roadmap

- [ ] Mobile fingerprinting support
- [ ] GUI interface
- [ ] Cloud profile storage
- [ ] Team collaboration features
- [ ] Advanced proxy rotation
- [ ] Cookie management
- [ ] Extension support

---

<div align="center">

**If this project helps you, don't forget to give it a ⭐!**

Made with ❤️ by [ToyryHoang](https://github.com/toyryhoang)

</div>
