import os
import time
import uuid
import random
import string
import datetime
import zipfile
import glob
import shutil
from generator import GoLogin
import traceback


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
def generate_profile_id():
    """Tạo ID profile duy nhất"""
    # Cách 1: Sử dụng timestamp + random
    timestamp = str(int(time.time() * 1000))  # milliseconds
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"P_{timestamp}_{random_suffix}"
    
    # Cách 2: Sử dụng UUID (comment out nếu dùng cách 1)
    # return f"P_{str(uuid.uuid4()).replace('-', '').upper()[:16]}"
    
    # Cách 3: Tương tự GoLogin generator (20 chữ số)
    # return ''.join(random.choices(string.digits, k=20))
def compress_profile(profile_id):
    """
    Nén thư mục profile thành file zip với xử lý quyền truy cập
    """
    try:
        profile_folder = os.path.join(os.getcwd(), 'temp', profile_id)
        zip_file = os.path.join(os.getcwd(), 'temp', f"{profile_id}.zip")
        
        if not os.path.exists(profile_folder):
            print(f"Không tìm thấy thư mục profile: {profile_folder}")
            return False
        
        print(f"Đang nén profile {profile_id}...")
        
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
        
        # Kiểm tra kích thước
        if os.path.exists(zip_file):
            compressed_size = os.path.getsize(zip_file)
            print(f"Đã nén profile thành công!")
            print(f"Kích thước nén: {compressed_size / (1024*1024):.2f} MB")
            return True
        else:
            print("Lỗi: File nén không được tạo")
            return False
        
    except Exception as e:
        print(f"Lỗi khi nén profile: {e}")
        return False

def decompress_profile(profile_id):
    """
    Giải nén profile từ file zip
    """
    try:
        zip_file = os.path.join(os.getcwd(), 'temp', f"{profile_id}.zip")
        profile_folder = os.path.join(os.getcwd(), 'temp', profile_id)
        
        if not os.path.exists(zip_file):
            print(f"Không tìm thấy file nén: {zip_file}")
            return False
        
        # Nếu thư mục đã tồn tại thì không cần giải nén
        if os.path.exists(profile_folder):
            print(f"Profile {profile_id} đã được giải nén")
            return True
        
        print(f"Đang giải nén profile {profile_id}...")
        
        with zipfile.ZipFile(zip_file, 'r') as zipf:
            zipf.extractall(profile_folder)
        
        print(f"Đã giải nén profile thành công!")
        return True
        
    except Exception as e:
        print(f"Lỗi khi giải nén profile: {e}")
        return False

def createProfile(name=None, proxy=None, auto_compress=True):
    """
    Tạo profile GoLogin với ID tự động
    """
    try:
        # Tạo ID tự động nếu không có name
        if name is None:
            profile_name = generate_profile_id()
        else:
            profile_name = name
            
        print(f"🆔 Profile Name/ID: {profile_name}")
        
        # Tạo thư mục temp nếu chưa tồn tại
        temp_dir = os.path.join(os.getcwd(), 'temp')
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            print(f"✅ Đã tạo thư mục temp: {temp_dir}")
        
        Runing = GoLogin({
            "tmpdir": temp_dir,
            "folderBrowser": os.path.join(os.getcwd(), '.gologin'),
        })
        detected_version = get_orbita_version()
        profile_config = {
            "version": detected_version,
            "os": 'win',
            "name": profile_name,  # Sử dụng ID tự động
            "canvas": {
                "mode": 'noise'
            },
            "canvasMode": 'noise',
            "webRTC": {
                "mode": 'noise',
            },
            "webRtc": {
                "mode": 'noise',
            },
            "webGL": {
                "mode": 'noise',
            },
            "audioContext": {
                "mode": True,
            },
            "clientRects": {
                "mode": True,
            },
            "geoLocation": {
                "mode": 'noise',
            },
            "geolocation": {
                "mode": 'noise',
            },
            "googleServicesEnabled": True,
            "doNotTrack": True
        }
        
        # Chỉ thêm proxy nếu được cung cấp
        if proxy:
            ip, port, username, password = proxy.split(':')
            profile_config["proxy"] = {
                'mode': "http",
                'host': ip,
                'port': port,
                'username': username,
                'password': password
            }
        
        print("🔄 Đang tạo profile...")
        profile_id = Runing.create(profile_config)
        
        if not profile_id:
            print("❌ Không thể tạo profile")
            return None
            
        print(f'✅ Profile ID: {profile_id}')
        print(f'📝 Profile Name: {profile_name}')
        
        # Phần còn lại giống như cũ...
        Runing.setProfileId(profile_id)
        
        profile_folder = os.path.join(temp_dir, profile_id)
        print(f"🔍 Kiểm tra thư mục profile: {profile_folder}")
        
        time.sleep(2)
        
        try:
            Runing.createStartup()
            print("✅ Đã tạo startup thành công")
        except Exception as e:
            print(f"⚠️ Lỗi khi tạo startup: {e}")
        
        if os.path.exists(profile_folder):
            if auto_compress:
                print("🗜️ Đang nén profile...")
                if compress_profile(profile_id):
                    print("✅ Đã nén profile thành công!")
                else:
                    print("⚠️ Không thể nén profile, nhưng profile vẫn khả dụng")
        else:
            print("❌ Thư mục profile không được tạo.")
            gologin_folder = os.path.join(os.getcwd(), '.gologin', profile_id)
            if os.path.exists(gologin_folder):
                print(f"🔍 Tìm thấy profile trong .gologin: {gologin_folder}")
                try:
                    shutil.copytree(gologin_folder, profile_folder)
                    print(f"📋 Đã copy profile sang temp folder")
                    if auto_compress:
                        compress_profile(profile_id)
                except Exception as e:
                    print(f"❌ Lỗi khi copy profile: {e}")
        
        return profile_id
        
    except Exception as e:
        print(f"❌ Lỗi khi tạo profile: {traceback.format_exc()}")
        return None

# Sử dụng:
if __name__ == "__main__":
    # Tạo profile với ID tự động
    profile_id = createProfile()
    print(f"✅ Đã tạo profile với ID: {profile_id}")
    # Hoặc tạo với name/ID tùy chỉnh
    # profile_id = createProfile("CUSTOM_ID_12345")
    
    # Với proxy
    # profile_id = createProfile(None, "192.168.1.1:8080:user:pass")