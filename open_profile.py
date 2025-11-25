import os
import requests
import subprocess
import re
import time
import zipfile
import threading
import urllib.request
import shutil
import psutil
import subprocess
import signal
import sys
import boto3
import glob
from botocore.client import Config
from generator import GoLogin
from selenium import webdriver
from selenium.webdriver.chrome.service import Service


def get_orbita_version():
	"""Tự động lấy version Orbita từ thư mục .gologin"""
	try:
		browser_path = os.path.join(os.getcwd(), '.gologin', 'browser')
		
		# Tìm thư mục orbita-browser-xxx
		orbita_dirs = glob.glob(os.path.join(browser_path, 'orbita-browser-*'))
		
		for orbita_dir in orbita_dirs:
			if os.path.isdir(orbita_dir) and not orbita_dir.endswith('.zip'):
				# Tìm version trong thư mục con
				version_dirs = glob.glob(os.path.join(orbita_dir, '*.*.*.*'))
				for version_dir in version_dirs:
					if os.path.isdir(version_dir):
						version = os.path.basename(version_dir)
						print(f"🔍 Phát hiện Orbita version: {version}")
						return version
		
		# Fallback về version mặc định
		print("⚠️ Không tìm thấy version, sử dụng mặc định")
		return '123.0.6312.59'
		
	except Exception as e:
		print(f"❌ Lỗi khi detect version: {e}")
		return '123.0.6312.59'

def upload_to_r2(zip_file_path, object_key):
	R2_ACCESS_KEY_ID = 'c5c32a584d3d082af4ebe4924e40fb91'
	R2_SECRET_ACCESS_KEY = 'da224053195a6753fba7c32bb66935f75bef0110fafa99536844e2f78c9f5b38'
	R2_BUCKET_NAME = 'zo8g-profile'
	R2_ACCOUNT_ID = 'd5505911d6c27bc6f2fc0bedb84ff27f'  # không có dấu ngoặc kép khi lấy từ dashboard

	session = boto3.session.Session()
	s3_client = session.client('s3',
		region_name='auto',
		endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
		aws_access_key_id=R2_ACCESS_KEY_ID,
		aws_secret_access_key=R2_SECRET_ACCESS_KEY,
		config=Config(signature_version='s3v4')
	)

	try:
		s3_client.upload_file(zip_file_path, R2_BUCKET_NAME, object_key)
		print(f"✅ Đã upload thành công: {object_key}")
	except Exception as e:
		print(f"❌ Upload thất bại: {e}")

def download_profile_from_r2(profile_id, save_dir='temp'):
	# Cấu hình R2
	R2_ACCESS_KEY_ID = 'c5c32a584d3d082af4ebe4924e40fb91'
	R2_SECRET_ACCESS_KEY = 'da224053195a6753fba7c32bb66935f75bef0110fafa99536844e2f78c9f5b38'
	R2_BUCKET_NAME = 'zo8g-profile'
	R2_ACCOUNT_ID = 'd5505911d6c27bc6f2fc0bedb84ff27f'  # không có dấu ngoặc kép khi lấy từ dashboard

	# File và object cần tải
	object_key = f"profiles/{profile_id}.zip"
	save_path = os.path.join(save_dir, f"{profile_id}.zip")

	# Tạo thư mục lưu nếu chưa có
	os.makedirs(save_dir, exist_ok=True)

	# Kết nối với Cloudflare R2
	session = boto3.session.Session()
	s3_client = session.client('s3',
		region_name='auto',
		endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
		aws_access_key_id=R2_ACCESS_KEY_ID,
		aws_secret_access_key=R2_SECRET_ACCESS_KEY,
		config=Config(signature_version='s3v4')
	)

	try:
		print(f"⬇️ Đang tải: {object_key}")
		s3_client.download_file(R2_BUCKET_NAME, object_key, save_path)
		print(f"✅ Đã tải về thành công: {save_path}")
		return save_path
	except Exception as e:
		print(f"❌ Lỗi khi tải profile: {e}")
		return None
	
class AutoMonitorProfileDriver:
	def __init__(self, driver, profile_id, auto_compress, gologin_instance, chrome_pid):
		self.driver = driver
		self.profile_id = profile_id
		self.auto_compress = auto_compress
		self.gologin_instance = gologin_instance
		self.chrome_pid = chrome_pid
		self.is_quit = False
		self.monitor_thread = None
		self.should_monitor = True
		self.input_interrupted = False
		
		# PHƯƠNG PHÁP CHÍNH XÁC NHẤT: Lấy từ Chrome capabilities
		self.debugger_port = None
		self.debugger_address = None
		
		try:
			# Driver được tạo với debuggerAddress option, không phải service args
			if hasattr(driver, 'capabilities'):
				chrome_options = driver.capabilities.get('goog:chromeOptions', {})
				debugger_address = chrome_options.get('debuggerAddress')
				
				if debugger_address:
					self.debugger_address = debugger_address
					port = debugger_address.split(':')[-1]
					self.debugger_port = int(port)
					print(f"📡 Debug port từ capabilities: {self.debugger_port}")
				else:
					print("⚠️ Không tìm thấy debuggerAddress trong capabilities")
					
		except Exception as e:
			print(f"⚠️ Lỗi khi lấy debug port: {e}")
		
		# Bật monitoring nếu có debug port
		if self.debugger_port:
			print(f"✅ Sẽ monitor qua debug port {self.debugger_port}")
			self.start_monitoring()
		else:
			print("⚠️ Không có debug port - Tắt auto-monitoring")
	
	def start_monitoring(self):
		"""Monitor Chrome bằng debug port thay vì PID"""
		def monitor_chrome():
			try:  
				# Lấy port từ debugger address
				if not hasattr(self, 'debugger_port'):
					# Extract port từ debugger_address của RunProfile
					port_match = re.search(r':(\d+)$', str(self.gologin_instance.start()))
					self.debugger_port = int(port_match.group(1)) if port_match else None
				
				if not self.debugger_port:
					print("⚠️ Không có debug port - Tắt monitoring")
					return
				
				print(f"👁️ Monitoring Chrome qua debug port {self.debugger_port}")
				
				# Đợi Chrome khởi động ổn định
				for i in range(10):
					if not self.should_monitor or self.is_quit:
						return
					time.sleep(1)
				
				consecutive_failures = 0
				max_failures = 2
				
				while self.should_monitor and not self.is_quit:
					try:
						# PHƯƠNG PHÁP CHÍNH: Kiểm tra debug port
						if self.is_chrome_debug_port_active():
							consecutive_failures = 0
						else:
							consecutive_failures += 1
							print(f"⚠️ Debug port không phản hồi (lần {consecutive_failures}/{max_failures})")
							
							if consecutive_failures >= max_failures:
								print("🔔 PHÁT HIỆN: Chrome đã đóng (debug port inactive)!")
								self.interrupt_input()
								self.auto_cleanup()
								break
						
					except Exception as e:
						consecutive_failures += 1
						print(f"⚠️ Lỗi monitoring (lần {consecutive_failures}/{max_failures}): {e}")
						
						if consecutive_failures >= max_failures:
							print("🔔 Chrome có thể đã đóng!")
							self.interrupt_input()
							self.auto_cleanup()
							break
					
					# Check interval
					for i in range(4):  # 4 giây
						if not self.should_monitor or self.is_quit:
							return
						time.sleep(1)
						
			except Exception as e:
				print(f"❌ Lỗi monitoring: {e}")
		
		self.monitor_thread = threading.Thread(target=monitor_chrome, daemon=True)
		self.monitor_thread.start()

	def is_chrome_debug_port_active(self):
		"""Kiểm tra Chrome debug port có active không"""
		try:
			import socket
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.settimeout(2)  # 2 giây timeout
			result = sock.connect_ex(('127.0.0.1', self.debugger_port))
			sock.close()
			
			if result == 0:
				# Port active, thử gọi API debug để chắc chắn
				try:
					import urllib.request
					url = f"http://127.0.0.1:{self.debugger_port}/json"
					req = urllib.request.Request(url)
					response = urllib.request.urlopen(req, timeout=2)
					data = response.read()
					return len(data) > 0  # Có phản hồi = Chrome còn sống
				except:
					return True  # Port mở = có thể Chrome còn sống
			
			return False
			
		except Exception:
			return False
	
	def interrupt_input(self):
		"""Interrupt input() khi Chrome đã tắt"""
		self.input_interrupted = True
		try:
			# Trên Windows, gửi Ctrl+C để interrupt input
			import os
			if os.name == 'nt':  # Windows
				import ctypes
				kernel32 = ctypes.windll.kernel32
				kernel32.GenerateConsoleCtrlEvent(0, 0)  # CTRL_C_EVENT
		except Exception as e:
			print(f"⚠️ Không thể interrupt input: {e}")
	
	def auto_cleanup(self):
		"""Tự động cleanup khi phát hiện Chrome đã tắt"""
		if self.is_quit:
			return
			
		print("🔄 TỰ ĐỘNG CLEANUP - User đã đóng Chrome!")
		self.is_quit = True
		self.should_monitor = False
		
		# Stop GoLogin profile
		try:
			print("🔄 Đang stop GoLogin profile...")
			self.gologin_instance.stop()
			print("✅ Đã stop GoLogin profile")
		except Exception as e:
			print(f"⚠️ Lỗi khi stop GoLogin: {e}")
		
		# Đợi lâu hơn để đảm bảo các process đã cleanup
		print("⏳ Đợi 5 giây để các process cleanup...")
		time.sleep(5)
		
		# Cleanup và nén profile
		if self.auto_compress:
			try:
				profile_folder = os.path.join(os.getcwd(), 'temp', self.profile_id)
				if os.path.exists(profile_folder):
					print("🧹 Đang dọn dẹp profile...")
					cleaned_size = cleanup_profile_before_compress(profile_folder)
					print(f"✅ Đã dọn dẹp {cleaned_size / (1024*1024):.1f} MB")
					
				print("🗜️ Đang tự động nén profile...")
				if compress_profile_after_use(self.profile_id):
					print("✅ Đã tự động nén profile thành công!")
				else:
					print("⚠️ Tự động nén profile thất bại")
					
			except Exception as compress_error:
				print(f"❌ Lỗi khi nén profile: {compress_error}")
		
		print("🎯 Hoàn thành tự động cleanup!")
		
		# Thoát chương trình sau khi cleanup
		print("🚪 Thoát chương trình...")
		os._exit(0)
	
	def __getattr__(self, name):
		"""Chuyển tiếp các method khác sang driver"""
		return getattr(self.driver, name)
	
	def quit(self):
		"""Quit thủ công"""
		if not self.is_quit:
			self.should_monitor = False  # Dừng monitoring
			
			try:
				self.driver.quit()
			except Exception as e:
				print(f"⚠️ Lỗi khi đóng driver: {e}")
			
			time.sleep(2)
			
			try:
				self.gologin_instance.stop()
			except Exception as e:
				print(f"⚠️ Lỗi khi stop GoLogin: {e}")
			
			self.is_quit = True
			time.sleep(3)
			
			if self.auto_compress:
				profile_folder = os.path.join(os.getcwd(), 'temp', self.profile_id)
				if os.path.exists(profile_folder):
					cleanup_profile_before_compress(profile_folder)
				print("🗜️ Đang nén profile...")
				compress_profile_after_use(self.profile_id)
def decompress_profile(profile_id):
	"""
	Kiểm tra và chuẩn bị profile (từ file zip hoặc folder có sẵn)
	"""
	try:
		# Profile lưu trong thư mục temp, không phải .gologin
		zip_file = os.path.join(os.getcwd(), 'temp', f"{profile_id}.zip")
		profile_folder = os.path.join(os.getcwd(), 'temp', profile_id)
		
		# Trường hợp 1: Thư mục profile đã tồn tại (chưa được nén)
		if os.path.exists(profile_folder):
			print(f"Profile {profile_id} đã sẵn sàng (dạng folder)")
			return True
		
		# Trường hợp 2: Có file zip, cần giải nén
		if os.path.exists(zip_file):
			
			try:
				with zipfile.ZipFile(zip_file, 'r') as zipf:
					zipf.extractall(profile_folder)
				
				# Xóa file zip sau khi giải nén thành công
				os.remove(zip_file)
				return True
				
			except Exception as extract_error:
				print(f"Lỗi khi giải nén: {extract_error}")
				# Nếu giải nén lỗi, xóa thư mục đã tạo (nếu có)
				if os.path.exists(profile_folder):
					try:
						shutil.rmtree(profile_folder)
					except:
						pass
				return False
		
		# Trường hợp 3: Không tìm thấy cả hai
		print(f"❌ Không tìm thấy profile {profile_id}")
		print(f"   - Không có file: {zip_file}")
		print(f"   - Không có folder: {profile_folder}")
		return False
		
	except Exception as e:
		print(f"Lỗi khi xử lý profile: {e}")
		return False

def check_profile_exists(profile_id):
	"""
	Kiểm tra profile có tồn tại không (dạng zip hoặc folder) trong thư mục temp
	"""
	zip_file = os.path.join(os.getcwd(), 'temp', f"{profile_id}.zip")
	profile_folder = os.path.join(os.getcwd(), 'temp', profile_id)
	
	if os.path.exists(profile_folder):
		return "folder"
	elif os.path.exists(zip_file):
		return "zip"
	else:
		return None

def compress_profile_after_use(profile_id):
	"""
	Nén thư mục profile thành file zip với xử lý quyền truy cập
	"""
	try:
		profile_folder = os.path.join(os.getcwd(), 'temp', profile_id)
		zip_file = os.path.join(os.getcwd(), 'temp', f"{profile_id}.zip")
		
		if not os.path.exists(profile_folder):
			print(f"Không tìm thấy thư mục profile: {profile_folder}")
			return False
		
		# Đợi một chút để đảm bảo các tiến trình đã giải phóng file
		time.sleep(3)
		
		# Thay đổi quyền truy cập cho tất cả file và thư mục
		try:
			for root, dirs, files in os.walk(profile_folder):
				# Thay đổi quyền cho thư mục
				try:
					os.chmod(root, 0o777)
				except:
					pass
				
				# Thay đổi quyền cho file
				for file in files:
					try:
						file_path = os.path.join(root, file)
						os.chmod(file_path, 0o777)
					except:
						pass
						
				# Thay đổi quyền cho thư mục con
				for dir in dirs:
					try:
						dir_path = os.path.join(root, dir)
						os.chmod(dir_path, 0o777)
					except:
						pass
		except Exception as e:
			print(f"Cảnh báo: Không thể thay đổi quyền truy cập: {e}")
		
		# Nén file với xử lý lỗi từng file
		with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
			for root, dirs, files in os.walk(profile_folder):
				for file in files:
					try:
						file_path = os.path.join(root, file)
						arcname = os.path.relpath(file_path, profile_folder)
						zipf.write(file_path, arcname)
					except (OSError, IOError, PermissionError) as e:
						print(f"Bỏ qua file không thể đọc: {file} - {e}")
						continue
		
		# Thử xóa thư mục với nhiều lần thử
		max_retries = 5
		for attempt in range(max_retries):
			try:
				# Thay đổi quyền truy cập lần nữa trước khi xóa
				for root, dirs, files in os.walk(profile_folder, topdown=False):
					for file in files:
						try:
							file_path = os.path.join(root, file)
							os.chmod(file_path, 0o777)
							# Thử xóa file trước
							os.remove(file_path)
						except:
							pass
					
					for dir in dirs:
						try:
							dir_path = os.path.join(root, dir)
							os.chmod(dir_path, 0o777)
							# Thử xóa thư mục rỗng
							os.rmdir(dir_path)
						except:
							pass
				
				# Cuối cùng xóa thư mục gốc
				if os.path.exists(profile_folder):
					os.chmod(profile_folder, 0o777)
					shutil.rmtree(profile_folder, ignore_errors=True)
				
				# Kiểm tra xem đã xóa thành công chưa
				if not os.path.exists(profile_folder):
					break
					
			except Exception as e:
				if attempt < max_retries - 1:
					print(f"Lần thử {attempt + 1}: Không thể xóa thư mục, thử lại sau 3 giây...")
					time.sleep(3)
				else:
					print(f"Cảnh báo: Không thể xóa hoàn toàn thư mục gốc: {e}")
					print("Profile đã được nén nhưng một số file/thư mục vẫn tồn tại")
		
		# Upload lên R2
		object_key = f"profiles/{profile_id}.zip"
		upload_to_r2(zip_file, object_key)
		
		# Kiểm tra kích thước và xóa file zip local sau khi upload thành công
		if os.path.exists(zip_file):
			compressed_size = os.path.getsize(zip_file)
			print(f"Kích thước nén: {compressed_size / (1024*1024):.2f} MB")
			
			# Xóa file zip local sau khi upload thành công
			try:
				os.remove(zip_file)
				print(f"✅ Đã xóa file zip local: {profile_id}.zip")
			except Exception as e:
				print(f"⚠️ Không thể xóa file zip local: {e}")
			
			return True
		else:
			print("Lỗi: File nén không được tạo")
			return False
		
	except Exception as e:
		print(f"Lỗi khi nén profile: {e}")
		return False

def download_chromedriver_for_version(chrome_version):
	"""Tải ChromeDriver cho phiên bản Chrome cụ thể"""
	try:
		# Lấy major version
		major_version = chrome_version.split('.')[0]
		
		# URL để lấy ChromeDriver cho version cụ thể
		url = f"https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
		response = requests.get(url, timeout=10)
		data = response.json()
		
		# Tìm version gần nhất với Chrome version
		compatible_versions = []
		for version_info in data['versions']:
			if version_info['version'].startswith(f"{major_version}."):
				compatible_versions.append(version_info)
		
		if not compatible_versions:
			print(f"Không tìm thấy ChromeDriver cho Chrome {major_version}")
			return None
			
		# Lấy version gần nhất
		target_version = sorted(compatible_versions, key=lambda x: x['version'])[-1]
		version_str = target_version['version']
		
		# Tìm download link cho Windows
		chromedriver_url = None
		for download in target_version['downloads'].get('chromedriver', []):
			if download['platform'] == 'win64':
				chromedriver_url = download['url']
				break
		
		if not chromedriver_url:
			print(f"Không tìm thấy ChromeDriver download link cho {version_str}")
			return None
		
		# Tạo thư mục driver nếu chưa có
		driver_dir = os.path.join(os.getcwd(), 'chromedriver')
		os.makedirs(driver_dir, exist_ok=True)
		
		# Đường dẫn file driver
		driver_path = os.path.join(driver_dir, f'chromedriver_{version_str}.exe')
		
		# Kiểm tra đã tải chưa
		if os.path.exists(driver_path):
			print(f"ChromeDriver {version_str} đã tồn tại")
			return driver_path
		
		# Tải file zip
		zip_path = os.path.join(driver_dir, f'chromedriver_{version_str}.zip')
		urllib.request.urlretrieve(chromedriver_url, zip_path)
		
		# Giải nén
		with zipfile.ZipFile(zip_path, 'r') as zip_ref:
			# Tìm file chromedriver.exe trong zip
			for file_info in zip_ref.filelist:
				if file_info.filename.endswith('chromedriver.exe'):
					# Giải nén với tên mới
					source = zip_ref.open(file_info)
					with open(driver_path, 'wb') as target:
						target.write(source.read())
					source.close()
					break
		
		# Xóa file zip
		os.remove(zip_path)
		return driver_path
		
	except Exception as e:
		print(f"Lỗi khi tải ChromeDriver: {e}")
		return None
def cleanup_profile_before_compress(profile_folder):
	"""Dọn dẹp profile triệt để trước khi nén"""
	try:
		
		# Danh sách đầy đủ hơn các items cần xóa
		cleanup_items = [
			# Cache directories (Windows paths)
			'Default\\Cache',
			'Default\\Code Cache', 
			'Default\\GPUCache',
			'Default\\Service Worker\\CacheStorage',
			'Default\\Application Cache',
			'Default\\Media Cache',
			'Default\\blob_storage',
			'GrShaderCache',
			'ShaderCache',
			
			# Log files và temp files
			'Default\\LOG',
			'Default\\LOG.old',
			'chrome_debug.log',
			'Default\\chrome_debug.log',
			'Default\\tmp',
			'Default\\Temp',
			'Crashpad',
			
			# Database cache và storage
			'Default\\IndexedDB',
			'Default\\Session Storage',
			'Default\\Local Storage',
			'Default\\databases',
			'Default\\FileSystem',
			'Default\\pepper_data',
			'Default\\Platform Notifications',
			'Default\\gcm_store',
			'Default\\AutofillStrikeDatabase',
			'Default\\BudgetDatabase',
			'Default\\optimization_guide_hint_cache_store',
			'Default\\Site Characteristics Database',
			'Default\\heavy_ad_intervention_opt_out.db',
			'Default\\commerce_subscription_db',
			'Default\\Reporting and NEL',
			'Default\\shared_proto_db',
			'Default\\trust_token_db',
			'Default\\Download Service',
			
			# Journal files - XÓA TẤT CẢ
			'Default\\History-journal',
			'Default\\Top Sites-journal',
			'Default\\Favicons-journal',
			'Default\\Web Data-journal',
			'Default\\Login Data-journal',
			'Default\\Cookies-journal',
			'Default\\Preferences-journal',
			'Default\\Affiliation Database-journal',
			'Default\\BrowsingTopicsSiteData-journal',
			'Default\\DIPS-journal',
			'Default\\Login Data For Account-journal',
			'Default\\MediaDeviceSalts-journal',
			'Default\\Shortcuts-journal',
			'Default\\Network\\Cookies-journal',
			'Default\\Network\\Reporting and NEL-journal',
			'Default\\Network\\Trust Tokens-journal',
			'Default\\Safe Browsing Network\\Safe Browsing Cookies-journal',
			'Default\\Shared Dictionary\\db-journal',
			'Default\\WebStorage\\QuotaManager-journal',
			'segmentation_platform\\ukm_db-journal',
			
			# Network và cache files
			'Default\\TransportSecurity',
			'Default\\QuotaManager',
			'Default\\QuotaManager-journal',
			'Default\\Network Action Predictor',
			'Default\\Network Action Predictor-journal',
			'Default\\Origin Bound Certs',
			'Default\\Origin Bound Certs-journal',
			
			# Thêm các thư mục/file mới phát hiện
			'AutofillStates',
			'BrowserMetrics', 
			'CertificateRevocation',
			'component_crx_cache',
			'segmentation_platform',
			
			# Extension-related IDs
			'biahpgbdmdkfgndcmfiipgcebobojjkp',
			'afalakplffnnnlkncjhbmahjfjhmlkal',
			'cffkpbalmllkdoenhmdmpbkajipdjfam',
			'enkheaiicpeffbfgjiklngbpkilnbkoi',
			'oofiananboodjbbmdelgdommihjbkfag',
			
			# System files
			'Dictionaries',
			'SafetyTips',
			'fonts',
		]
		
		cleaned_size = 0
		cleaned_count = 0
		
		# Dọn dẹp từng item
		for item in cleanup_items:
			item_path = os.path.join(profile_folder, item)
			if os.path.exists(item_path):
				try:
					if os.path.isdir(item_path):
						size_before = get_folder_size_bytes(item_path)
						shutil.rmtree(item_path, ignore_errors=True)
						cleaned_size += size_before
						cleaned_count += 1
					elif os.path.isfile(item_path):
						size_before = os.path.getsize(item_path)
						os.remove(item_path)
						cleaned_size += size_before
						cleaned_count += 1
				except Exception as e:
					print(f"   ⚠️ Không thể xóa {item}: {e}")
					continue
		
		# Xóa TẤT CẢ các file .tmp, .log, *-journal, .dmp trong toàn bộ profile
		try:
			import glob
			dangerous_patterns = [
				'**/*.tmp',
				'**/*.log', 
				'**/*-journal',
				'**/*.dmp',
				'**/LOG*',
				'**/CrashpadMetrics*',
				'**/JumpListIcons*/*.tmp',
			]
			
			for pattern in dangerous_patterns:
				full_pattern = os.path.join(profile_folder, pattern)
				for file_path in glob.glob(full_pattern, recursive=True):
					try:
						if os.path.isfile(file_path):
							size_before = os.path.getsize(file_path)
							os.remove(file_path)
							cleaned_size += size_before
							cleaned_count += 1
							rel_path = os.path.relpath(file_path, profile_folder)
					except Exception:
						continue
		except Exception as e:
			print(f"   ⚠️ Lỗi khi xóa files theo pattern: {e}")
		
		# Xóa extensions cache
		try:
			extensions_path = os.path.join(profile_folder, 'Default', 'Extensions')
			if os.path.exists(extensions_path):
				for ext_folder in os.listdir(extensions_path):
					ext_path = os.path.join(extensions_path, ext_folder)
					if os.path.isdir(ext_path):
						# Xóa cache trong từng extension
						for cache_folder in ['CacheStorage', 'Cache', 'Code Cache', 'Temp']:
							cache_path = os.path.join(ext_path, cache_folder)
							if os.path.exists(cache_path):
								size_before = get_folder_size_bytes(cache_path)
								shutil.rmtree(cache_path, ignore_errors=True)
								cleaned_size += size_before
								cleaned_count += 1
		except Exception as e:
			print(f"   ⚠️ Lỗi khi xóa extension cache: {e}")
		
		# Reset một số database về kích thước tối thiểu (EXPERIMENTAL)
		try:
			db_files_to_reset = [
				'Default\\History',
				'Default\\Top Sites', 
				'Default\\Favicons',
				'segmentation_platform\\ukm_db',
			]
			
			for db_file in db_files_to_reset:
				db_path = os.path.join(profile_folder, db_file)
				if os.path.exists(db_path):
					try:
						# Backup size
						size_before = os.path.getsize(db_path)
						if size_before > 1024 * 1024:  # Chỉ reset file > 1MB
							# Tạo file database rỗng/tối thiểu (CHỈ LÀM NẾU CẦN)
							# os.truncate() hoặc xử lý database khác ở đây
							print(f"   🔄 Database {db_file}: {size_before / (1024*1024):.1f} MB (giữ nguyên)")
					except Exception:
						continue
		except Exception:
			pass
		
		# Báo cáo kết quả
		if cleaned_size > 0:
			print(f"   🎯 Đã dọn dẹp {cleaned_count} items, tiết kiệm: {cleaned_size / (1024*1024):.1f} MB")
		else:
			print("   ℹ️ Không có dữ liệu cache để xóa")
		
		return cleaned_size
			
	except Exception as e:
		print(f"   ⚠️ Lỗi khi dọn dẹp: {e}")
		return 0
def get_folder_size_bytes(folder_path):
	"""Tính kích thước thư mục (bytes)"""
	total_size = 0
	try:
		for root, dirs, files in os.walk(folder_path):
			for file in files:
				try:
					total_size += os.path.getsize(os.path.join(root, file))
				except:
					continue
	except:
		pass
	return total_size
def openProfile(profile_id, proxy=None, auto_compress_after=True):
	"""
	Mở profile GoLogin với ID đã cho
	profile_id: ID của profile cần mở  
	proxy: 
		- Non-auth: "ip:port" 
		- Auth: "ip:port:username:password"
		- None: không proxy
	auto_compress_after: tự động nén lại sau khi đóng
	"""
	RunProfile = None
	driver = None
	
	try:
		print(f"Đang khởi tạo profile: {profile_id}")
		
		# Kiểm tra profile có tồn tại không
		profile_status = check_profile_exists(profile_id)
		if profile_status is None:
			print(f"❌ Profile {profile_id} không tồn tại!")
			return None
		
		print(f"✅ Tìm thấy profile (dạng: {profile_status})")
		
		# Chuẩn bị profile (giải nén nếu cần)
		if not decompress_profile(profile_id):
			print("❌ Không thể chuẩn bị profile")
			return None
		
		# **XỬ LÝ PROXY - THÊM/SỬA/XÓA**
		profile_folder = os.path.join(os.getcwd(), 'temp', profile_id)
		preferences_file = os.path.join(profile_folder, 'Default', 'Preferences')
		
		if os.path.exists(preferences_file):
			try:
				import json
				
				# Đọc preferences
				with open(preferences_file, 'r', encoding='utf-8') as f:
					preferences = json.load(f)
				
				if proxy:
					# CÓ PROXY - Cập nhật proxy mới
					print(f"🌐 Đang cập nhật proxy: {proxy}")
					
					# Parse proxy - PHÂN BIỆT 2 LOẠI
					proxy_parts = proxy.split(':')
					
					if len(proxy_parts) == 2:
						# Non-auth proxy: ip:port
						ip, port = proxy_parts
						proxy_config = {
							'mode': 'http',
							'host': ip,
							'port': int(port)
						}
						print(f"✅ Proxy Non-Auth: {ip}:{port}")
						
					elif len(proxy_parts) == 4:
						# Auth proxy: ip:port:username:password
						ip, port, username, password = proxy_parts
						proxy_config = {
							'mode': 'http',
							'host': ip,
							'port': int(port),
							'username': username,
							'password': password
						}
						print(f"✅ Proxy Auth: {ip}:{port} (User: {username})")
						
					else:
						print("❌ Format proxy không đúng!")
						print("   - Non-auth: ip:port")
						print("   - Auth: ip:port:username:password")
						return None
					
					# Cập nhật proxy
					if 'gologin' not in preferences:
						preferences['gologin'] = {}
					preferences['gologin']['proxy'] = proxy_config
					
				else:
					# KHÔNG PROXY - Xóa proxy cũ nếu có
					if 'gologin' in preferences and 'proxy' in preferences['gologin']:
						old_proxy = preferences['gologin']['proxy']
						print(f"🚫 Đang xóa proxy cũ: {old_proxy.get('host', 'N/A')}:{old_proxy.get('port', 'N/A')}")
						
						# Xóa proxy khỏi preferences
						del preferences['gologin']['proxy']
						
						# Nếu gologin section rỗng, xóa luôn
						if not preferences['gologin']:
							del preferences['gologin']
							
						print("✅ Đã xóa proxy cũ - Profile sẽ chạy direct connection")
					else:
						print("ℹ️ Không có proxy - Profile sẽ chạy direct connection")
				
				# Lưu lại preferences
				with open(preferences_file, 'w', encoding='utf-8') as f:
					json.dump(preferences, f, indent=2, ensure_ascii=False)
				
			except Exception as e:
				print(f"⚠️ Lỗi khi xử lý proxy: {e}")
				return None
		
		# Tạo thư mục .gologin nếu cần cho browser
		gologin_dir = os.path.join(os.getcwd(), '.gologin')
		os.makedirs(gologin_dir, exist_ok=True)
		
		RunProfile = GoLogin({
			"profile_id": profile_id,
			"folderBrowser": gologin_dir,
			"tmpdir": os.path.join(os.getcwd(), 'temp')
		})

		print("🚀 Đang start profile...")
		debugger_address = RunProfile.start()
		
		if debugger_address is None:
			print("❌ Không thể start profile")
			return None
			
		print(f"✅ Debugger address: {debugger_address}")

		# Phần còn lại giữ nguyên...
		detected_version = get_orbita_version()
		chromedriver_path = download_chromedriver_for_version(detected_version)
		user_agent = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{detected_version} Safari/537.36"
		if chromedriver_path and os.path.exists(chromedriver_path):
			service = Service(executable_path=chromedriver_path)
		else:
			service = None

		chrome_options = webdriver.ChromeOptions()
		chrome_options.add_experimental_option("debuggerAddress", debugger_address)
		chrome_options.add_argument("--no-sandbox")
		chrome_options.add_argument(f"--user-agent={user_agent}")
		chrome_options.add_argument("--disable-dev-shm-usage")

		if service:
			driver = webdriver.Chrome(service=service, options=chrome_options)
		else:
			driver = webdriver.Chrome(options=chrome_options)
		
		driver.set_window_position(0, 0)
		driver.set_window_size(800, 600)
		
		print(f"✅ Đã mở profile thành công: {profile_id}")
		chrome_pid = None
		try:
			# Tìm Chrome process bằng port debugger - CẢI THIỆN
			port = debugger_address.split(':')[-1]
			print(f"🔍 Đang tìm Chrome process với port {port}...")
			
			# Đợi một chút để Chrome process ổn định
			time.sleep(2)
			
			for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status']):
				try:
					if proc.info['name'] and 'chrome' in proc.info['name'].lower():
						cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
						if f'--remote-debugging-port={port}' in cmdline:
							# Kiểm tra process có đang chạy không
							if proc.info['status'] == psutil.STATUS_RUNNING:
								chrome_pid = proc.info['pid']
								print(f"🔍 Tìm thấy Chrome PID: {chrome_pid} (status: {proc.info['status']})")
								break
				except (psutil.NoSuchProcess, psutil.AccessDenied):
					continue
					
			if not chrome_pid:
				print("⚠️ Không tìm thấy Chrome PID - Auto-monitoring sẽ bị vô hiệu hóa")
				
		except Exception as e:
			print(f"⚠️ Không thể lấy Chrome PID: {e}")
		
		
		return AutoMonitorProfileDriver(driver, profile_id, auto_compress_after, RunProfile, chrome_pid)
		
	except Exception as e:
		print(f"❌ Lỗi khi mở profile: {e}")
		
		# CLEANUP NGAY KHI CÓ LỖI
		print("🔄 Đang cleanup do lỗi xảy ra...")
		
		# Đóng driver nếu đã tạo
		if driver:
			try:
				driver.quit()
				print("✅ Đã đóng Selenium driver")
			except:
				pass
		
		# Stop GoLogin nếu đã start
		if RunProfile:
			try:
				RunProfile.stop()
				print("✅ Đã stop GoLogin profile")
			except:
				pass
		
		time.sleep(3)
		
		# Nén profile nếu yêu cầu
		if auto_compress_after:
			profile_folder = os.path.join(os.getcwd(), 'temp', profile_id)
			if os.path.exists(profile_folder):
				print("🧹 Đang dọn dẹp profile...")
				cleanup_profile_before_compress(profile_folder)
				
			print("🗜️ Đang nén profile do lỗi...")
			if compress_profile_after_use(profile_id):
				print("✅ Đã nén profile thành công!")
			else:
				print("⚠️ Nén profile thất bại")
		
		return None

def createAndOpenProfile(profile_name):
	"""
	Tạo profile mới và mở nó
	profile_name: tên profile
	"""
	try:
		print(f"Đang tạo profile mới: {profile_name}")
		
		# Tạo thư mục .gologin nếu cần
		gologin_dir = os.path.join(os.getcwd(), '.gologin')
		os.makedirs(gologin_dir, exist_ok=True)
		
		Runing = GoLogin({
			"tmpdir": os.path.join(os.getcwd(), 'temp'),
			"folderBrowser": gologin_dir,
		})
		
		# Sử dụng version ổn định
		detected_version = get_orbita_version()
		
		profile_config = {
			"version": detected_version,
			"os": 'win',
			"name": profile_name,
			"canvas": {"mode": 'noise'},
			"canvasMode": 'noise',
			"webRTC": {"mode": 'noise'},
			"webRtc": {"mode": 'noise'},
			"webGL": {"mode": 'noise'},
			"audioContext": {"mode": True},
			"clientRects": {"mode": True},
			"geoLocation": {"mode": 'noise'},
			"geolocation": {"mode": 'noise'},
			"googleServicesEnabled": True,
			"doNotTrack": True
		}   
		
		profile_id = Runing.create(profile_config)  
		if profile_id:
			print(f"Đã tạo profile thành công với ID: {profile_id}")
			return openProfile(profile_id)
		else:
			print("Không thể tạo profile")
			return None
	except Exception as e:
		print(f"Lỗi khi tạo profile: {e}")
		import traceback
		traceback.print_exc()
		return None

def list_profiles_simple():
	"""
	Liệt kê nhanh các profile có sẵn trong thư mục temp
	"""
	try:
		temp_dir = os.path.join(os.getcwd(), 'temp')
		if not os.path.exists(temp_dir):
			print("❌ Không tìm thấy thư mục temp")
			return []
		
		profiles = []
		
		print("\n📋 Danh sách profile trong temp:")
		print("-" * 50)
		
		# Danh sách thư mục hệ thống cần bỏ qua
		system_folders = [
			'browser', 'cache', 'logs', 'temp_data'
		]
		
		# Tìm các thư mục profile (chỉ ID số)
		for item in os.listdir(temp_dir):
			# Bỏ qua thư mục hệ thống
			if item.lower() in [f.lower() for f in system_folders]:
				continue
				
			item_path = os.path.join(temp_dir, item)
			
			# Kiểm tra nếu là thư mục và có dạng ID (chỉ số)
			if os.path.isdir(item_path) and item.isdigit():
				folder_size = get_folder_size(item_path)
				print(f"📁 {item} - Folder ({folder_size:.1f} MB)")
				profiles.append(item)
		
		# Tìm các file zip (chỉ ID số)
		for item in os.listdir(temp_dir):
			if item.endswith('.zip'):
				profile_id = item[:-4]  # Bỏ phần .zip
				
				# Chỉ xử lý nếu profile_id là số và chưa có trong danh sách
				if profile_id.isdigit() and profile_id not in profiles:
					zip_size = os.path.getsize(os.path.join(temp_dir, item)) / (1024*1024)
					print(f"📦 {profile_id} - Compressed ({zip_size:.1f} MB)")
					profiles.append(profile_id)
		
		print("-" * 50)
		print(f"Tổng cộng: {len(profiles)} profile(s)")
		
		return profiles
		
	except Exception as e:
		print(f"❌ Lỗi khi liệt kê profile: {e}")
		return []

def get_folder_size(folder_path):
	"""Tính kích thước thư mục (MB)"""
	total_size = 0
	try:
		for root, dirs, files in os.walk(folder_path):
			for file in files:
				total_size += os.path.getsize(os.path.join(root, file))
	except:
		pass
	return total_size / (1024*1024)

if __name__ == "__main__":
	
	# Thử profile cụ thể
	profile_id = "05606404270909730014"
	if profile_id:
		driver = openProfile(profile_id)
		if driver:
			print("✅ Profile đã được mở thành công!")
			input("⏸️ Nhấn Enter để đóng trình duyệt...")
			driver.quit()
		else:
			print("❌ Không thể mở profile!")
	else:
		print(f"\n❌ Profile {profile_id} không tồn tại trong temp!")