import json
import string
import time
import os
import stat
import sys
import shutil
import uuid

import requests
import zipfile
import subprocess
import pathlib
import tempfile
import math
import socket
import random
import psutil
import datetime
# extensionsManager
from extensionsManager import ExtensionsManager

API_URL = 'https://api.gologin.com'
PROFILES_URL = 'https://gprofiles-new.gologin.com/'


class GoLogin(object):
    def __init__(self, options):
        self.profile_path = None
        self.profile = None
        self.proxy = None
        self.access_token = options.get('token')
        self.profile_id = options.get('profile_id')
        self.tmpdir = options.get('tmpdir', tempfile.gettempdir())
        self.address = options.get('address', '127.0.0.1')
        self.extra_params = options.get('extra_params', [])
        self.port = options.get('port', 3500)
        self.local = options.get('local', False)
        self.spawn_browser = options.get('spawn_browser', True)
        self.credentials_enable_service = options.get('credentials_enable_service')
        self.cleaningLocalCookies = options.get('cleaningLocalCookies', False)
        self.executablePath = ''
        self.is_new_cloud_browser = options.get('is_new_cloud_browser', True)
        self.FrontList = None
        self.families = None
        self.Ner_fingerprint_profile = None
        self.folderBroser = options.get('folderBrowser', '.gologin')
        home = str(pathlib.Path.home())
        self.browser_gologin = os.path.join(home, self.folderBroser, 'browser')
        try:
            for orbita_browser in os.listdir(self.browser_gologin):
                if not orbita_browser.endswith('.zip') and not orbita_browser.endswith(
                        '.tar.gz') and orbita_browser.startswith('orbita-browser'):
                    self.executablePath = options.get('executablePath',
                                                      os.path.join(self.browser_gologin, orbita_browser, 'chrome'))
                    if not os.path.exists(self.executablePath) and not orbita_browser.endswith(
                            '.tar.gz') and sys.platform == "darwin":
                        self.executablePath = os.path.join(home, self.browser_gologin, orbita_browser,
                                                           'Orbita-Browser.app/Contents/MacOS/Orbita')

        except Exception as e:
            self.executablePath = ''

        if not self.executablePath:
            raise Exception(
                f"Orbita executable file not found in HOME ({self.browser_gologin}). Is gologin installed on your system?")

        if self.extra_params:
            print('extra_params', self.extra_params)
        self.setProfileId(options.get('profile_id'))
        self.preferences = {}
        self.pid = int()

    def setProfileId(self, profile_id):
        self.profile_id = profile_id
        if self.profile_id == None:
            return
        self.profile_path = os.path.join(self.tmpdir, self.profile_id)
        # print(f"==>> self.profile_path: {self.profile_path}")
        self.profile_zip_path = os.path.join(self.tmpdir, self.profile_id + '.zip')
        # print(f"==>> self.profile_zip_path: {self.profile_zip_path}")
        self.profile_zip_path_upload = os.path.join(self.tmpdir, self.profile_id + '_upload.zip')
        


    def spawnBrowser(self):
        pref_file = os.path.join(self.profile_path, 'Default', 'Preferences')
        with open(pref_file, 'r', encoding="utf-8") as pfile:
            preferences = json.load(pfile)
        try:
            proxy = preferences.get('gologin').get('proxy')
        except:
            proxy = None
        self.port = getRandomPort()
        if proxy:
            if proxy.get('mode') == None or proxy.get('mode') == 'geolocation':
                proxy['mode'] = 'http'
            proxy_host = proxy.get('host')
            proxy = self.formatProxyUrl(proxy)

        # tz = self.tz.get('timezone')
        params = [
            self.executablePath,
            '--remote-debugging-port=' + str(self.port),
            '--user-data-dir=' + self.profile_path,
            '--disable-encryption',
            '--password-store=basic',
            '--donut-pie={test:test}',
        ]

        # chromeExtensions = self.profile.get('chromeExtensions')
        # if chromeExtensions and len(chromeExtensions) > 0:
        #     paths = self.loadExtensions()
        #     if paths is not None:
        #         extToParams = '--load-extension=' + paths
        #         params.append(extToParams)

        if proxy:
            hr_rules = '"MAP * 0.0.0.0 , EXCLUDE %s"' % (proxy_host)
            params.append('--proxy-server=' + proxy)
            params.append('--host-resolver-rules=' + hr_rules)

        for param in self.extra_params:
            params.append(param)

        if sys.platform == "darwin":
            open_browser = subprocess.Popen(params)
            self.pid = open_browser.pid
        else:
            open_browser = subprocess.Popen(params, start_new_session=True)
            self.pid = open_browser.pid

        try_count = 1
        url = self.address + ':' + str(self.port)
        while try_count < 100:
            try:
                data = requests.get('http://' + url + '/json').content
                break
            except:
                try_count += 1
                time.sleep(1)
        return url

    def start(self):
        # profile_path = self.createStartup()
        # print(profile_path)
        self.profile_path = self.getProfilePath()
        url = self.spawnBrowser()
        return url


    def zipdir(self, path, ziph):
        for root, dirs, files in os.walk(path):
            for file in files:
                path = os.path.join(root, file)
                if not os.path.exists(path):
                    continue
                if stat.S_ISSOCK(os.stat(path).st_mode):
                    continue
                try:
                    ziph.write(path, path.replace(self.profile_path, ''))
                except:
                    continue

    def waitUntilProfileUsing(self, try_count=0):
        if try_count > 10:
            return
        time.sleep(1)
        profile_path = self.profile_path
        if os.path.exists(profile_path):
            try:
                os.rename(profile_path, profile_path)
            except OSError as e:
                # print("waiting chrome termination")
                self.waitUntilProfileUsing(try_count + 1)

    def stop(self):
        for proc in psutil.process_iter(['pid']):
            if proc.info.get('pid') == self.pid:
                proc.kill()
        self.waitUntilProfileUsing()
        self.sanitizeProfile()
        
        #if self.local == False:
        #    self.commitProfile()
        #    os.remove(self.profile_zip_path_upload)
        #    shutil.rmtree(self.profile_path)

    def commitProfile(self):
        zipf = zipfile.ZipFile(self.profile_zip_path_upload, 'w', zipfile.ZIP_DEFLATED)
        self.zipdir(self.profile_path, zipf)
        zipf.close()

        # headers = {
        #     'Authorization': 'Bearer ' + self.access_token,
        #     'User-Agent': 'Selenium-API'
        # }
        # # print('profile size=', os.stat(self.profile_zip_path_upload).st_size)

        # signedUrl = requests.get(API_URL + '/browser/' + self.profile_id + '/storage-signature',
        #                          headers=headers).content.decode('utf-8')

        # requests.put(signedUrl, data=open(self.profile_zip_path_upload, 'rb'))

        # print('commit profile complete')

    def sanitizeProfile(self):
        # Tắt tính năng xóa cookies
        #if (self.cleaningLocalCookies):
        #    path_to_coockies = os.path.join(self.profile_path, 'Default', 'Network', 'Cookies')
        #    os.remove(path_to_coockies)

        remove_dirs = [
            # Cache directories (chiếm nhiều dung lượng nhất)
            'Default/Cache',
            'Default/Service Worker/CacheStorage',
            'Default/Code Cache',
            'Default/GPUCache',
            'Default/Application Cache',
            'Default/Media Cache',
            'Default/blob_storage',
            'GrShaderCache',
            'ShaderCache',
            
            # Log files
            'Default/LOG',
            'Default/LOG.old',
            'chrome_debug.log',
            
            # Temporary files
            'Default/tmp',
            'Default/Temp',
            'Crashpad',
            
            # Database và storage cache
            'Default/IndexedDB',
            'Default/Session Storage',
            'Default/Local Storage',
            'Default/databases',
            'Default/FileSystem',
            'Default/pepper_data',
            'Default/Platform Notifications',
            'Default/gcm_store',
            'Default/AutofillStrikeDatabase',
            'Default/BudgetDatabase',
            'Default/optimization_guide_hint_cache_store',
            'Default/Site Characteristics Database',
            'Default/heavy_ad_intervention_opt_out.db',
            'Default/commerce_subscription_db',
            'Default/Reporting and NEL',
            'Default/shared_proto_db',
            'Default/trust_token_db',
            'Default/Download Service',
            
            # Extension cache
            'Default/Extensions/*/CacheStorage',
            
            # Extension IDs (giữ nguyên từ code cũ)
            'biahpgbdmdkfgndcmfiipgcebobojjkp',
            'afalakplffnnnlkncjhbmahjfjhmlkal',
            'cffkpbalmllkdoenhmdmpbkajipdjfam',
            'enkheaiicpeffbfgjiklngbpkilnbkoi',
            'oofiananboodjbbmdelgdommihjbkfag',
            
            # Dictionaries và fonts (có thể tái tạo)
            'Dictionaries',
            'SafetyTips',
            'fonts',
            
            # Journal files và temp files patterns
            'Default/History-journal',
            'Default/Top Sites-journal',
            'Default/Favicons-journal',
            'Default/Web Data-journal',
            'Default/Login Data-journal',
            'Default/Preferences-journal',
            'Default/Cookies-journal',
            'Default/TransportSecurity',
            'Default/QuotaManager',
            'Default/QuotaManager-journal',
        ]

        for d in remove_dirs:
            # Xử lý wildcard patterns
            if '*' in d:
                import glob
                pattern = os.path.join(self.profile_path, d.replace('/', os.sep))
                for match_path in glob.glob(pattern):
                    try:
                        if os.path.isdir(match_path):
                            shutil.rmtree(match_path, ignore_errors=True)
                    except:
                        continue
            else:
                # Xử lý paths thông thường
                fpath = os.path.join(self.profile_path, d.replace('/', os.sep))
                if os.path.exists(fpath):
                    try:
                        if os.path.isdir(fpath):
                            shutil.rmtree(fpath)
                        elif os.path.isfile(fpath):
                            os.remove(fpath)
                    except:
                        continue

    def formatProxyUrl(self, proxy):
        # Kiểm tra proxy có None hoặc rỗng không
        if not proxy:
            return None
        
        # Đảm bảo các giá trị proxy không phải None
        mode = proxy.get('mode', 'http') or 'http'
        host = proxy.get('host', '') or ''
        port = proxy.get('port', 80) or 80
        
        # Nếu host rỗng hoặc None thì không thể tạo proxy URL
        if not host:
            return None
            
        return mode + '://' + host + ':' + str(port)

    def formatProxyUrlPassword(self, proxy):
        mode = "socks5h" if proxy.get("mode") == "socks5" else proxy.get("mode", "http")
        if proxy.get('username', '') == '':
            return mode + '://' + proxy.get('host', '') + ':' + str(proxy.get('port', 80))
        else:
            return proxy.get('mode', 'http') + '://' + proxy.get('username', '') + ':' + proxy.get(
                'password') + '@' + proxy.get('host', '') + ':' + str(proxy.get('port', 80))

    def getTimeZone(self):
        proxy = self.proxy
        try:
            if proxy:
                proxies = {
                    'http': self.formatProxyUrlPassword(proxy),
                    'https': self.formatProxyUrlPassword(proxy)
                }
                data = requests.get('https://time.gologin.com', proxies=proxies)
            else:
                data = requests.get('https://time.gologin.com')

            return json.loads(data.content.decode('utf-8'))
        except:
            return json.loads('{"ip":"14.244.14.164","country":"VN","stateProv":"Phú Thọ Province","city":"Việt Trì","timezone":"Asia/Bangkok","ll":["21.31920","105.40310"],"languages":"vi","accuracy":100}')

    def getProfile(self, profile_id=None):
        profile = self.profile_id if profile_id == None else profile_id
        data = self.Ner_fingerprint_profile
        return data


    def getProfilePath(self):
        ProfilePath = os.path.join(self.tmpdir, self.profile_id)
        return ProfilePath

    def downloadProfileZip(self):
        try:
            self.createEmptyProfile()
            self.extractProfileZip()
        except:
            self.uploadEmptyProfile()
            self.createEmptyProfile()
            self.extractProfileZip()

        if not os.path.exists(os.path.join(self.profile_path, 'Default', 'Preferences')):
            self.uploadEmptyProfile()
            self.createEmptyProfile()
            self.extractProfileZip()

    def uploadEmptyProfile(self):
        # print('uploadEmptyProfile')
        upload_profile = open(r'./gologin_zeroprofile.zip', 'wb')
        source = requests.get(PROFILES_URL + 'zero_profile.zip')
        upload_profile.write(source.content)
        upload_profile.close()

    def createEmptyProfile(self):
        # print('createEmptyProfile')
        empty_profile = '../gologin_zeroprofile.zip'
        if not os.path.exists(empty_profile):
            empty_profile = 'gologin_zeroprofile.zip'
        shutil.copy(empty_profile, self.profile_zip_path)

    def extractProfileZip(self):
        with zipfile.ZipFile(self.profile_zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.profile_path)
        os.remove(self.profile_zip_path)

    def getGeolocationParams(self, profileGeolocationParams, tzGeolocationParams):
        if profileGeolocationParams.get('fillBasedOnIp'):
            return {
                'mode': profileGeolocationParams['mode'],
                'latitude': float(tzGeolocationParams['latitude']),
                'longitude': float(tzGeolocationParams['longitude']),
                'accuracy': float(tzGeolocationParams['accuracy']),
            }

        return {
            'mode': profileGeolocationParams['mode'],
            'latitude': profileGeolocationParams['latitude'],
            'longitude': profileGeolocationParams['longitude'],
            'accuracy': profileGeolocationParams['accuracy'],
        }


    def convertPreferences(self, preferences):
        resolution = preferences.get('navigator', {}).get('resolution')
        preferences['screenWidth'] = int(resolution.split('x')[0])
        preferences['screenHeight'] = int(resolution.split('x')[1])
        now = datetime.datetime.now()
        formatted_datetime = now.strftime("%d/%m/%Y %H:%M")
        preferences['notes'] = str(formatted_datetime)

        self.tz = self.getTimeZone()
        # print('tz=', self.tz)

        tzGeoLocation = {
            'latitude': self.tz.get('ll', [0, 0])[0],
            'longitude': self.tz.get('ll', [0, 0])[1],
            'accuracy': self.tz.get('accuracy', 0),
        }
        tzgeolocation = {
            "accuracy": self.tz.get('accuracy', 0),
            "customize": True,
            "enabled": True,
            "fillBasedOnIp": True,
            'latitude': self.tz.get('ll', [0, 0])[0],
            'longitude': self.tz.get('ll', [0, 0])[1],
            "mode": preferences.get('geolocation', {}).get('mode'),
        }

        preferences['geoLocation'] = tzGeoLocation
        preferences['geolocation'] = tzgeolocation

        preferences['webRTC'] = {
            'customize': True,
            'enabled': True,
            'fillBasedOnIp': True,
            'localIpMasking': True,
            "fill_based_on_ip": True,
            "local_ip_masking": True,
            'mode': preferences.get('webRTC', {}).get('mode')
            if preferences.get('webRTC', {}).get('mode') == 'public'
            else preferences.get('webRTC', {}).get('mode'),
            'publicIp': self.tz.get('query')
            if preferences.get('webRTC', {}).get('fillBasedOnIp')
            else preferences.get('webRTC', {}).get('publicIp'),
            'localIps': preferences.get('webRTC', {}).get('localIps', []),
        }

        preferences['webRtc'] = {
            'customize': True,
            'enabled': True,
            'fillBasedOnIp': True,
            'localIpMasking': True,
            "fill_based_on_ip": True,
            "local_ip_masking": True,
            'mode': preferences.get('webRTC', {}).get('mode')
            if preferences.get('webRTC', {}).get('mode') == 'public'
            else preferences.get('webRTC', {}).get('mode'),
            'publicIP': self.tz.get('query')
            if preferences.get('webRTC', {}).get('fillBasedOnIp')
            else preferences.get('webRTC', {}).get('publicIp'),
            'publicIp': self.tz.get('query')
            if preferences.get('webRTC', {}).get('fillBasedOnIp')
            else preferences.get('webRTC', {}).get('publicIp'),
            'localIps': preferences.get('webRTC', {}).get('localIps', []),
            'public_ip': self.tz.get('query')
            if preferences.get('webRTC', {}).get('fillBasedOnIp')
            else preferences.get('webRTC', {}).get('publicIp')
        }

        preferences['timezone'] = {
            'id': self.tz.get('timezone')
        }

        # if preferences.get('webGLMetadata', {}).get('mode'):
        #     preferences.get('webGLMetadata', {})['mode'] = 'mask'
        # preferences['webGLMetadata'] = preferences.get('webGLMetadata', {})
        preferences['webglParams'] = preferences.get('webglParams', {})
        preferences['webgl_noise_value'] = preferences.get('webGL', {}).get('noise')
        preferences['webglNoiseValue'] = preferences.get('webGL', {}).get('noise')

        preferences['webglNoiceEnable'] = preferences.get('webGL', {}).get('mode')
        preferences['webgl_noise_enable'] = preferences.get('webGL', {}).get('mode')
        preferences['webgl_noice_enable'] = preferences.get('webGL', {}).get('mode')

        preferences['langHeader'] = preferences.get('navigator', {}).get('language', {})
        if preferences.get('storage', {}):
            preferences.get('storage', {})['enable'] = True
        preferences['get_client_rects_noise'] = preferences.get('webGL', {}).get('getClientRectsNoise')
        preferences['getClientRectsNoice'] = preferences.get('webGL', {}).get('getClientRectsNoise')
        preferences['client_rects_noise_enable'] = preferences.get('clientRects', {}).get('mode')
        preferences['canvasMode'] = preferences.get('canvas', {}).get('mode')
        preferences['canvasNoise'] = preferences.get('canvas', {}).get('noise')
        # preferences['audioContextMode'] = preferences.get('audioContext', {}).get('mode')

        preferences['icon'] = {
            "avatar": {
                "enabled": True,
                "horizontal_position": 2,
                "vertical_position": 2
            },
            "text": preferences.get('name')
        }
        preferences['plugins'] = {
            "all_enable": preferences.get('plugins', {}).get('enableVulnerable'),
            "flash_enable": preferences.get('plugins', {}).get('enableFlash')
        }
        preferences['audioContext'] = {
            'enable': preferences.get('audioContext').get('mode'),
            'noiseValue': float(preferences.get('audioContext').get('noise')),
        }
        list_videoInputs = [0, 1, 1, 1, 1, 1, 1]
        list_audioInputs = [0, 1, 1, 1, 2, 2, 2, 3, 4]
        list_audioOutputs = [0, 1, 1, 1, 2, 2, 2, 3, 4]
        new_videoInputs = random.choice(list_videoInputs)
        new_audioInputs = random.choice(list_audioInputs)
        new_audioOutputs = random.choice(list_audioOutputs)
        preferences['mediaDevices']['videoInputs'] = new_videoInputs
        preferences['mediaDevices']['audioInputs'] = new_audioInputs
        preferences['mediaDevices']['audioOutputs'] = new_audioOutputs
        preferences['mediaDevices']['enable'] = True
        preferences['webGl'] = {
            'metadata': {
                'vendor': preferences.get('webGLMetadata', {}).get('vendor'),
                'renderer': preferences.get('webGLMetadata', {}).get('renderer'),
                'mode': preferences.get('webGLMetadata', {}).get('mode') == 'mask',
            }
        }

        preferences['webgl'] = {
            'metadata': {
                'vendor': preferences.get('webGLMetadata', {}).get('vendor'),
                'renderer': preferences.get('webGLMetadata', {}).get('renderer'),
                'mode': preferences.get('webGLMetadata', {}).get('mode') == 'mask',
            }
        }
        list_hardwareConcurrency = [2, 2, 2, 4, 4, 4, 4, 8, 8, 8, 12]
        new_hardwareConcurrency = random.choice(list_hardwareConcurrency)
        list_deviceMemory = [4, 4, 4, 4, 8, 8, 8, 8, 16]
        new_deviceMemory = random.choice(list_deviceMemory)
        if preferences.get('navigator', {}).get('userAgent'):
            if preferences.get('os') == "android" or preferences.get('os') == "iphone":
                cover = (preferences.get('navigator', {}).get('userAgent')).replace('Safari', 'Mobile Safari')
                preferences['userAgent'] = cover
                preferences['navigator']['userAgent'] = cover
            else:
                preferences['userAgent'] = preferences.get('navigator', {}).get('userAgent')
                preferences['navigator']['hardwareConcurrency'] = new_hardwareConcurrency
                preferences['navigator']['deviceMemory'] = new_deviceMemory

        if preferences.get('navigator', {}).get('doNotTrack'):
            preferences['doNotTrack'] = preferences.get('navigator', {}).get('doNotTrack')

        if preferences.get('navigator', {}).get('hardwareConcurrency'):
            preferences['hardwareConcurrency'] = preferences.get('navigator', {}).get('hardwareConcurrency')
            preferences['deviceMemory'] = new_deviceMemory * 1024

        if preferences.get('navigator', {}).get('language'):
            preferences['language'] = preferences.get('navigator', {}).get('language')
            preferences['languages'] = (preferences.get('navigator', {}).get('language')).split(';')[0]
        if preferences.get('isM1', False):
            preferences["is_m1"] = preferences.get('isM1', False)

        if preferences.get('os') == "android" or preferences.get('os') == "iphone":
            devicePixelRatio = preferences.get("devicePixelRatio")
            deviceScaleFactorCeil = math.ceil(devicePixelRatio or 3.5);
            deviceScaleFactor = devicePixelRatio
            if deviceScaleFactorCeil == devicePixelRatio:
                deviceScaleFactor += 0.00000001

            preferences["mobile"] = {
                "enable": True,
                "width": preferences['screenWidth'],
                "height": preferences['screenHeight'],
                "device_scale_factor": deviceScaleFactor,
            }
        else:
            devicePixelRatio = preferences.get("devicePixelRatio")
            deviceScaleFactorCeil = math.ceil(devicePixelRatio or 3.5);
            deviceScaleFactor = devicePixelRatio
            if deviceScaleFactorCeil == devicePixelRatio:
                deviceScaleFactor += 0.00000001
            preferences["mobile"] = {
                "enable": False,
                "width": preferences['screenWidth'],
                "height": preferences['screenHeight'],
                "device_scale_factor": deviceScaleFactor,
            }
        if preferences.get('proxy'):
            preferences["proxy"] = {
                "id": preferences.get('proxy', {}).get('id'),
                'mode': preferences.get('proxy', {}).get('mode'),
                'host': preferences.get('proxy', {}).get('host'),
                'port': preferences.get('proxy', {}).get('port'),
                'username': preferences.get('proxy', {}).get('username'),
                'password': preferences.get('proxy', {}).get('password'),
                'changeIpUrl': preferences.get('proxy', {}).get('changeIpUrl'),
                'autoProxyRegion': False,
                'torProxyRegion': False
            }
        return preferences

    def updatePreferences(self):
        pref_file = os.path.join(self.profile_path, 'Default', 'Preferences')
        with open(pref_file, 'r', encoding="utf-8") as pfile:
            preferences = json.load(pfile)
        profile = self.profile
        profile['profile_id'] = self.profile_id
        proxy = self.profile.get('proxy')
        # print('proxy=', proxy)
        if proxy and (proxy.get('mode') == 'gologin' or proxy.get('mode') == 'tor'):
            autoProxyServer = profile.get('autoProxyServer')
            splittedAutoProxyServer = autoProxyServer.split('://')
            splittedProxyAddress = splittedAutoProxyServer[1].split(':')
            port = splittedProxyAddress[1]
            proxy = {
                'mode': 'http',
                'host': splittedProxyAddress[0],
                'port': port,
                'username': profile.get('autoProxyUsername'),
                'password': profile.get('autoProxyPassword'),
                'timezone': profile.get('autoProxyTimezone', 'us'),
            }

            profile['proxy']['username'] = profile.get('autoProxyUsername')
            profile['proxy']['password'] = profile.get('autoProxyPassword')

        if not proxy or proxy.get('mode') == 'none':
            # print('no proxy')
            proxy = None

        if proxy and proxy.get('mode') == 'geolocation':
            proxy['mode'] = 'http'

        if proxy and proxy.get('mode') == None:
            proxy['mode'] = 'http'
        self.FrontList = profile.get('fonts').get('families')
        self.proxy = proxy
        self.profile_name = profile.get('name')
        gologin = self.convertPreferences(profile)
        if self.credentials_enable_service != None:
            preferences['credentials_enable_service'] = self.credentials_enable_service
        preferences['gologin'] = gologin
        with open(pref_file, 'w', encoding='utf-8') as pfile:
            json.dump(preferences, pfile, ensure_ascii=False)
        pfile.close()

    def read_fonts(self):
        with open("fonts.json", "r") as f:
            config = json.load(f)
            f.close()
        return config

    def coppy_front(self, result):
        try:
            os.mkdir(f"{self.profile_path}\\fonts")
            fontPath = os.path.join(self.browser_gologin, 'fonts')
            for font in self.families:
                if font['name'] in result:
                    file_name = font["fileNames"][0]
                    pathFronts = os.path.join(fontPath, f'{file_name}')
                    pathPr = os.path.join(self.profile_path, 'fonts', f'{file_name}')
                    if os.path.exists(pathFronts):
                        shutil.copyfile(pathFronts, pathPr)
        except Exception as d:
            print(d)


    def compare_front(self, FrontList, families):
        result = []
        for font in FrontList:
            if font in families:
                result.append(font)
        self.coppy_front(result)

    def GenFont(self):
        self.families = self.read_fonts()
        Frontfamilies = [font['name'] for font in self.families]
        self.compare_front(self.FrontList, Frontfamilies)

    def add_extension(self):
        shutil.copytree("cookies-ext", f"{self.profile_path}\\extensions\\cookies-ext")
        with open(f"{self.profile_path}\\extensions\\cookies-ext\\uid.json", 'w') as f:
            f.write(json.dumps(
                {
                    "uid": self.profile_id,
                    "port": 36912
                }
            ))


    def createStartup(self):
        try:
            if not self.local:
                self.downloadProfileZip()
            self.profile = self.getProfile()

            self.updatePreferences()
            self.add_extension()
            self.GenFont()
        except Exception as a:
            print('createStartup', a)
        return self.profile_path

    def headers(self):
        return {
            'Authorization': 'Bearer ' + self.access_token,
            'User-Agent': 'Selenium-API'
        }
    def generateWindowsFingerprint(self, options):
        """
        Tạo fingerprint Windows thực tế dựa trên máy tính tầm trung và cao cấp 5 năm gần đây
        """
        self.tz = self.getTimeZone()
        timezone_id = self.tz.get('timezone')
        country_code = self.tz.get('country')
        geo_lat = self.tz.get('ll', [0, 0])[0]
        geo_lon = self.tz.get('ll', [0, 0])[1]
        geo_accuracy = self.tz.get('accuracy', 0)
        public_ip = self.tz.get('ip')
        # Mapping quốc gia sang ngôn ngữ (cập nhật với các ngôn ngữ phổ biến theo quốc gia)
        country_language_map = {
            'US': {'language': 'en-US', 'langs': ['en-US', 'en']},
            'GB': {'language': 'en-GB', 'langs': ['en-GB', 'en']},
            'CA': {'language': 'en-CA', 'langs': ['en-CA', 'en', 'fr-CA']},
            'AU': {'language': 'en-AU', 'langs': ['en-AU', 'en']},
            'NZ': {'language': 'en-NZ', 'langs': ['en-NZ', 'en']},
            'DE': {'language': 'de-DE', 'langs': ['de-DE', 'de', 'en']},
            'AT': {'language': 'de-AT', 'langs': ['de-AT', 'de', 'en']},
            'CH': {'language': 'de-CH', 'langs': ['de-CH', 'de', 'fr-CH', 'it-CH']},
            'FR': {'language': 'fr-FR', 'langs': ['fr-FR', 'fr', 'en']},
            'ES': {'language': 'es-ES', 'langs': ['es-ES', 'es', 'en']},
            'MX': {'language': 'es-MX', 'langs': ['es-MX', 'es', 'en']},
            'IT': {'language': 'it-IT', 'langs': ['it-IT', 'it', 'en']},
            'PT': {'language': 'pt-PT', 'langs': ['pt-PT', 'pt', 'en']},
            'BR': {'language': 'pt-BR', 'langs': ['pt-BR', 'pt', 'en']},
            'NL': {'language': 'nl-NL', 'langs': ['nl-NL', 'nl', 'en']},
            'BE': {'language': 'nl-BE', 'langs': ['nl-BE', 'fr-BE', 'en']},
            'RU': {'language': 'ru-RU', 'langs': ['ru-RU', 'ru', 'en']},
            'UA': {'language': 'uk-UA', 'langs': ['uk-UA', 'uk', 'ru', 'en']},
            'JP': {'language': 'ja-JP', 'langs': ['ja-JP', 'ja', 'en']},
            'CN': {'language': 'zh-CN', 'langs': ['zh-CN', 'zh', 'en']},
            'TW': {'language': 'zh-TW', 'langs': ['zh-TW', 'zh', 'en']},
            'HK': {'language': 'zh-HK', 'langs': ['zh-HK', 'zh', 'en']},
            'KR': {'language': 'ko-KR', 'langs': ['ko-KR', 'ko', 'en']},
            'TH': {'language': 'th-TH', 'langs': ['th-TH', 'th', 'en']},
            'VN': {'language': 'vi-VN', 'langs': ['vi-VN', 'vi', 'en-US', 'en']},
            'ID': {'language': 'id-ID', 'langs': ['id-ID', 'id', 'en']},
            'MY': {'language': 'ms-MY', 'langs': ['ms-MY', 'ms', 'en']},
            'PH': {'language': 'fil-PH', 'langs': ['fil-PH', 'en-PH', 'en']},
            'IN': {'language': 'hi-IN', 'langs': ['hi-IN', 'en-IN', 'en']},
            'TR': {'language': 'tr-TR', 'langs': ['tr-TR', 'tr', 'en']},
            'PL': {'language': 'pl-PL', 'langs': ['pl-PL', 'pl', 'en']},
            'RO': {'language': 'ro-RO', 'langs': ['ro-RO', 'ro', 'en']},
        }
        
        # Mặc định ngôn ngữ là tiếng Anh nếu không tìm thấy country code
        default_language = {'language': 'en-US', 'langs': ['en-US', 'en']}
        
        # Lấy ngôn ngữ dựa trên country code
        language_info = country_language_map.get(country_code, default_language)
        browser_language = language_info['language']
        browser_languages = language_info['langs']
        
        # Format chuỗi accept-language theo chuẩn HTTP
        accept_language = browser_language + ';q=1.0'
        for i, lang in enumerate(browser_languages[1:], 1):
            q_value = 1.0 - (i * 0.1)
            if q_value > 0:
                accept_language += f',{lang};q={q_value:.1f}'
        
        # Screen resolutions phổ biến cho máy tính tầm trung và cao cấp (5 năm gần đây)
        screen_resolutions = [
            {"width": 1920, "height": 1080, "weight": 35},  # Full HD phổ biến nhất
            {"width": 2560, "height": 1440, "weight": 22},  # QHD phổ biến cho PC cao cấp
            {"width": 3840, "height": 2160, "weight": 10},  # 4K
            {"width": 1536, "height": 864, "weight": 12},   # Laptop phổ biến
            {"width": 1440, "height": 900, "weight": 8},    # Laptop cao cấp
            {"width": 3440, "height": 1440, "weight": 5},   # Ultrawide
            {"width": 2560, "height": 1600, "weight": 8},   # 16:10 cao cấp
        ]
        
        # Chọn resolution theo trọng số
        weights = [r["weight"] for r in screen_resolutions]
        resolution = random.choices(screen_resolutions, weights=weights)[0]
        
        # Chrome versions mới (cập nhật 2024)
        chrome_versions = [
            "123.0.6312.86", "122.0.6261.112", "121.0.6167.140", 
            "120.0.6099.217", "119.0.6045.199", "118.0.5993.89"
        ]
        chrome_version = random.choice(chrome_versions)
        
        # User agents Windows mới nhất
        base_ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
        
        # WebGL vendors/renderers cho GPU phổ biến 5 năm gần đây
        gpu_configs = [
            # NVIDIA 
            {
                "vendor": "Google Inc. (NVIDIA)",
                "renderer": "ANGLE (NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0)"
            },
            {
                "vendor": "Google Inc. (NVIDIA)",
                "renderer": "ANGLE (NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0)"
            },
            {
                "vendor": "Google Inc. (NVIDIA)",
                "renderer": "ANGLE (NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)"
            },
            {
                "vendor": "Google Inc. (NVIDIA)",
                "renderer": "ANGLE (NVIDIA GeForce RTX 2080 SUPER Direct3D11 vs_5_0 ps_5_0)"
            },
            {
                "vendor": "Google Inc. (NVIDIA)",
                "renderer": "ANGLE (NVIDIA GeForce RTX 2070 SUPER Direct3D11 vs_5_0 ps_5_0)"
            },
            {
                "vendor": "Google Inc. (NVIDIA)",
                "renderer": "ANGLE (NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0)"
            },
            # AMD
            {
                "vendor": "Google Inc. (AMD)",
                "renderer": "ANGLE (AMD Radeon RX 5700 XT Direct3D11 vs_5_0 ps_5_0)"
            },
            # Intel
            {
                "vendor": "Google Inc. (Intel)",
                "renderer": "ANGLE (Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)"
            },
            {
                "vendor": "Google Inc. (Intel)",
                "renderer": "ANGLE (Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0)"
            }
        ]
        webgl_config = random.choice(gpu_configs)
        
        # Hardware specs phổ biến cho máy tính tầm trung và cao cấp
        hardware_configs = [
            {"cores": 4, "memory": 8},   # Tầm trung
            {"cores": 6, "memory": 8},   # Tầm trung
            {"cores": 6, "memory": 16},  # Tầm trung cao
            {"cores": 8, "memory": 16},  # Cao cấp
            {"cores": 8, "memory": 32},  # Cao cấp
            {"cores": 12, "memory": 32}, # Cao cấp
            {"cores": 16, "memory": 32}  # Rất cao cấp
        ]
        hardware = random.choice(hardware_configs)
        
        # Font danh sách Windows thực tế
        windows_fonts = [
            "Arial", "Arial Black", "Bahnschrift", "Calibri", "Cambria", 
            "Cambria Math", "Candara", "Comic Sans MS", "Consolas", 
            "Constantia", "Corbel", "Courier New", "Ebrima", 
            "Franklin Gothic Medium", "Gabriola", "Gadugi", "Georgia", 
            "Impact", "Leelawadee UI", "Lucida Console", 
            "Lucida Sans Unicode", "Malgun Gothic", "Microsoft Sans Serif", 
            "Microsoft YaHei", "Mongolian Baiti", "MS Gothic",
            "MV Boli", "Nirmala UI", "Palatino Linotype",
            "Segoe Print", "Segoe Script", "Segoe UI",
            "Segoe UI Symbol", "SimSun", "Sitka", "Sylfaen", "Symbol", 
            "Tahoma", "Times New Roman", "Trebuchet MS", "Verdana", 
            "Webdings", "Wingdings", "Yu Gothic"
        ]
        
        # Thêm random fonts bổ sung (70% máy tính có font bổ sung)
        additional_fonts = ["Roboto", "Open Sans", "Lato", "Montserrat", "Source Sans Pro"]
        if random.random() < 0.7:
            windows_fonts.extend(random.sample(additional_fonts, random.randint(1, 3)))
        
        # Device pixel ratio hợp lý theo resolution
        if resolution["width"] >= 3840:  # 4K
            device_pixel_ratio = 2.0
        elif resolution["width"] >= 2560:  # QHD
            device_pixel_ratio = random.choice([1.5, 2.0])
        else:
            device_pixel_ratio = random.choice([1.0, 1.25])
        # Tạo fingerprint cuối cùng
        fingerprint = {
            "name": options.get('name', 'Default Profile'),
            "os": "win",
            "navigator": {
                "userAgent": base_ua,
                "resolution": f"{resolution['width']}x{resolution['height']}",
                "language": accept_language,  # Đã cập nhật ngôn ngữ theo vị trí địa lý
                "platform": "Win32",
                "hardwareConcurrency": hardware["cores"],
                "deviceMemory": hardware["memory"],
                "maxTouchPoints": 0,
                "doNotTrack": random.choice([True, False]),
                "cookieEnabled": True,
                "webdriver": False
            },
            "screen": {
                "width": resolution["width"],
                "height": resolution["height"],
                "availWidth": resolution["width"],
                "availHeight": resolution["height"] - 40,  # Taskbar
                "colorDepth": 24,
                "pixelDepth": 24
            },
            "webGL": {
                "vendor": webgl_config["vendor"],
                "renderer": webgl_config["renderer"],
                "mode": options.get('webGL', {}).get('mode', 'noise'),
                "noise": round(random.uniform(1, 10), 2)
            },
            "webGLMetadata": {
                "vendor": webgl_config["vendor"],
                "renderer": webgl_config["renderer"],
                "mode": "mask"
            },
            "canvas": {
                "mode": options.get('canvas', {}).get('mode', 'noise'),
                "noise": round(random.uniform(0.1, 5.0), 2)
            },
            "webRTC": {
                "mode": options.get('webRTC', {}).get('mode', 'altered'),
                "fillBasedOnIp": True,
                "publicIp": public_ip
            },
            "audioContext": {
                "mode": options.get('audioContext', {}).get('mode', True),
                "noise": "{:.12e}".format(round(random.uniform(0.00000000001, 0.0000001), 20))
            },
            "clientRects": {
                "mode": options.get('clientRects', {}).get('mode', True),
                "noise": round(random.uniform(1, 5), 2)
            },
            "timezone": {
                "id": timezone_id  # Timezone theo IP máy
            },
            "geolocation": {
                "mode": options.get('geolocation', {}).get('mode', 'noise'),
                "latitude": geo_lat,
                "longitude": geo_lon,
                "accuracy": geo_accuracy,
                "fillBasedOnIp": True
            },
            "fonts": {
                "families": windows_fonts,
                "mode": "mask"
            },
            "mediaDevices": {
                "videoInputs": random.choice([0, 1, 1, 1, 2]),
                "audioInputs": random.choice([1, 1, 2, 2]),
                "audioOutputs": random.choice([1, 1, 2, 2]),
                "uid": uuid.uuid4().hex + uuid.uuid4().hex[:38]  # Unique ID
            },
            "plugins": {
                "enableVulnerable": False,
                "enableFlash": False
            },
            "storage": {
                "localStorage": True,
                "sessionStorage": True,
                "indexedDB": True,
                "webSQL": False
            },
            "devicePixelRatio": device_pixel_ratio,
            "languages": browser_languages  # Thêm mảng ngôn ngữ để đảm bảo nhất quán
        }
        
        return fingerprint
    def getRandomFingerprint(self, options):
        check_os = options.get('os')
        if check_os == 'win':
            return self.generateWindowsFingerprint(options)

        if check_os == 'mac':
            selected_file = random.choice(os.listdir(f"{os.getcwd()}\\fingerprints\\MacOS_Fingerprint"))
            random_p = json.loads(open(os.path.join(f"{os.getcwd()}\\fingerprints\\MacOS_Fingerprint", selected_file), 'r', encoding="utf8").read())
        
        if check_os == 'lin':
            selected_file = random.choice(os.listdir(f"{os.getcwd()}\\fingerprints\\Lin_Fingerprint"))
            random_p = json.loads(open(os.path.join(f"{os.getcwd()}\\fingerprints\\Lin_Fingerprint", selected_file), 'r', encoding="utf8").read())
        
        if check_os == 'android':   
            selected_file = random.choice(os.listdir(f"{os.getcwd()}\\fingerprints\\Android_Fingerprint"))
            random_p = json.loads(open(os.path.join(f"{os.getcwd()}\\fingerprints\\Android_Fingerprint", selected_file), 'r', encoding="utf8").read())
        print(f"🖐️ Đang sử dụng fingerprint: {selected_file}")
        return random_p['Gologin']

    def profiles(self):
        return json.loads(requests.get(API_URL + '/browser/', headers=self.headers()).content.decode('utf-8'))

    def create(self, options={}):
        profile_options = self.getRandomFingerprint(options)
        navigator = options.get('navigator')
        version_orbita = options.get('version')
        old_ua_browser = profile_options.get('navigator', {}).get('userAgent')
        old_ver_browser = old_ua_browser.split('Chrome/')
        old_ver_browser = old_ver_browser[1].split(' ')
        new_ua = old_ua_browser.replace(old_ver_browser[0], version_orbita)
        if new_ua:
            profile_options['navigator']['userAgent'] = new_ua
        # Thêm userAgent
        # if options.get('navigator'):
        #     resolution = navigator.get('resolution')
        #     if resolution == 'random':
        #         resolution = profile_options['navigator']['resolution']
        #     userAgent = navigator.get('userAgent')
        #     if userAgent == 'random':
        #         userAgent = profile_options['navigator']['userAgent']
        #
        #     if resolution == 'random' or userAgent == 'random':
        #         profile_options['navigator']['resolution'] = resolution
        #         profile_options['navigator']['userAgent'] = userAgent
        #     if resolution != 'random' and userAgent != 'random':
        #         profile_options['navigator']['resolution'] = resolution
        #         profile_options['navigator']['userAgent'] = userAgent
        #     if resolution == 'random' and userAgent != 'random':
        #         profile_options['navigator']['userAgent'] = userAgent
        #     if userAgent == 'random' and resolution != 'random':
        #         profile_options['navigator']['resolution'] = resolution
        #
        #     language = navigator.get('language')
        #     profile_options['navigator']['language'] = language
        profile_options['webGL']['mode'] = options.get('webGL').get('mode')
        profile_options['audioContext']['mode'] = options.get('audioContext').get('mode')
        profile_options['clientRects']['mode'] = options.get('clientRects').get('mode')
        profile_options['canvas']['mode'] = options.get('canvas').get('mode')
        name = options.get('name')
        n = 0
        if name != 'random':
            n += 1
            profile_options['name'] = f"{'{:04}'.format(n)}_{name}"
        profile_options['googleServicesEnabled'] = options.get('googleServicesEnabled')
        profile_options['navigator']['doNotTrack'] = options.get('doNotTrack')
        if options.get('proxy'):
            profile_options['proxy'] = options.get('proxy')
            # print(options.get('proxy'))
        profile_options['canvas']['mode'] = options.get('canvas', {}).get('mode')
        profile_options['canvas']['noise'] = round(random.uniform(0.1, 9.5), 8)
        profile_options['webGL']['noise'] = round(random.uniform(1, 95), 3)
        profile_options['webGL']['getClientRectsNoise'] = int(round(random.uniform(1, 10), 5))
        profile_options['clientRects']['noise'] = profile_options['webGL']['getClientRectsNoise']
        audioContext_noise = "{:.12e}".format(round(random.uniform(0.00000000001, 0.0000001), 20))
        profile_options['audioContext']['noise'] = audioContext_noise
        uid_mediaDevices = uuid.uuid4().hex
        uid_mediaDevices2 = uuid.uuid4().hex
        uids_mediaDevices = (uid_mediaDevices + uid_mediaDevices2)[:58]
        profile_options['mediaDevices']['uid'] = uids_mediaDevices
        profile_options['webRTC']['mode'] = options.get('webRTC', {}).get('mode')
        profile_options['geolocation']['mode'] = options.get('geolocation', {}).get('mode')
        # check_os = options.get('os', {})
        # if check_os != 'android' or check_os != 'iphone':
        #     profile_options['fonts'] = options.get('fonts', {})

        self.Ner_fingerprint_profile = profile_options
        letters = string.digits
        id_profile = ''.join(random.choice(letters) for i in range(20))
        return id_profile

    def delete(self, profile_id=None):
        profile = self.profile_id if profile_id == None else profile_id
        requests.delete(API_URL + '/browser/' + profile, headers=self.headers())

    def update(self, options):
        self.profile_id = options.get('id')
        profile = self.getProfile()
        # print("profile", profile)
        for k, v in options.items():
            profile[k] = v
        resp = requests.put(API_URL + '/browser/' + self.profile_id, headers=self.headers(),
                            json=profile).content.decode('utf-8')
        # print("update", resp)
        # return json.loads(resp)

    def waitDebuggingUrl(self, delay_s, remote_orbita_url, try_count=3):
        url = remote_orbita_url + '/json/version'
        wsUrl = ''
        try_number = 1
        while wsUrl == '':
            time.sleep(delay_s)
            try:
                response = json.loads(requests.get(url).content)
                wsUrl = response.get('webSocketDebuggerUrl', '')
            except:
                pass
            if try_number >= try_count:
                return {'status': 'failure', 'wsUrl': wsUrl}
            try_number += 1

        remote_orbita_url_without_protocol = remote_orbita_url.replace('https://', '')
        wsUrl = wsUrl.replace('ws://', 'wss://').replace('127.0.0.1', remote_orbita_url_without_protocol)

        return {'status': 'success', 'wsUrl': wsUrl}

    def startRemote(self, delay_s=3):
        responseJson = requests.post(
            API_URL + '/browser/' + self.profile_id + '/web',
            headers=self.headers(),
            json={'isNewCloudBrowser': self.is_new_cloud_browser}
        ).content.decode('utf-8')
        response = json.loads(responseJson)
        print('profileResponse', response)

        remote_orbita_url = 'https://' + self.profile_id + '.orbita.gologin.com'
        if self.is_new_cloud_browser:
            if not response['remoteOrbitaUrl']:
                raise Exception('Couldn\' start the remote browser')
            remote_orbita_url = response['remoteOrbitaUrl']

        return self.waitDebuggingUrl(delay_s, remote_orbita_url=remote_orbita_url)

    def stopRemote(self):
        response = requests.delete(
            API_URL + '/browser/' + self.profile_id + '/web',
            headers=self.headers(),
            params={'isNewCloudBrowser': self.is_new_cloud_browser}
        )

    def clearCookies(self, profile_id=None):
        self.cleaningLocalCookies = True

        profile = self.profile_id if profile_id == None else profile_id
        resp = requests.post(API_URL + '/browser/' + profile + '/cookies?cleanCookies=true', headers=self.headers(),
                             json=[])

        if resp.status_code == 204:
            return {'status': 'success'}
        else:
            return {'status': 'failure'}

    async def normalizePageView(self, page):
        if self.preferences.get("screenWidth") == None:
            self.profile = self.getProfile()
            self.preferences['screenWidth'] = int(self.profile.get("navigator").get("resolution").split('x')[0])
            self.preferences['screenHeight'] = int(self.profile.get("navigator").get("resolution").split('x')[1])
        width = self.preferences.get("screenWidth")
        height = self.preferences.get("screenHeight")
        await page.setViewport({"width": width, "height": height});


def getRandomPort():
    while True:
        port = random.randint(1000, 35000)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        if result == 0:
            continue
        else:
            return port
        sock.close()
