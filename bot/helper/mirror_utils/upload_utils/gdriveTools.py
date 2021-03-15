import os
import pickle
import urllib.parse as urlparse
from urllib.parse import parse_qs
from bot import LOGGER

import json
import logging
import re
import requests
import socket

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from tenacity import *

from telegram import InlineKeyboardMarkup
from bot.helper.telegram_helper import button_build
from telegraph import Telegraph

from bot import parent_id, DOWNLOAD_DIR, IS_TEAM_DRIVE, INDEX_URL, \
    USE_SERVICE_ACCOUNTS, download_dict, telegraph_token, BUTTON_THREE_NAME, BUTTON_THREE_URL, BUTTON_FOUR_NAME, BUTTON_FOUR_URL, BUTTON_FIVE_NAME, BUTTON_FIVE_URL, SHORTENER, SHORTENER_API
from bot.helper.ext_utils.bot_utils import *
from bot.helper.ext_utils.fs_utils import get_mime_type, get_path_size
from bot.config import IS_TEAM_DRIVE, \
            USE_SERVICE_ACCOUNTS, GDRIVE_FOLDER_ID, INDEX_URL


LOGGER = logging.getLogger(__name__)
logging.getLogger('googleapiclient.discovery').setLevel(logging.ERROR)
socket.setdefaulttimeout(650) # https://github.com/googleapis/google-api-python-client/issues/632#issuecomment-541973021
SERVICE_ACCOUNT_INDEX = 0
TELEGRAPHLIMIT = 95

def clean_name(name):
    name = name.replace("'", "\\'")
    return name

class GoogleDriveHelper:
    def __init__(self, name=None, listener=None, GFolder_ID=GDRIVE_FOLDER_ID):
        self.__G_DRIVE_TOKEN_FILE = "token.pickle"
        # Check https://developers.google.com/drive/scopes for all available scopes
        self.__OAUTH_SCOPE = ['https://www.googleapis.com/auth/drive']
        # Redirect URI for installed apps, can be left as is
        self.__REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
        self.__G_DRIVE_DIR_MIME_TYPE = "application/vnd.google-apps.folder"
        self.__G_DRIVE_BASE_DOWNLOAD_URL = "https://drive.google.com/uc?id={}&export=download"
        self.__G_DRIVE_DIR_BASE_DOWNLOAD_URL = "https://drive.google.com/drive/folders/{}"
        self.__listener = listener
        self.__service = self.authorize()
        self.__listener = listener
        self._file_uploaded_bytes = 0
        self.uploaded_bytes = 0
        self.UPDATE_INTERVAL = 5
        self.start_time = 0
        self.total_time = 0
        self._should_update = True
        self.is_uploading = True
        self.is_cancelled = False
        self.status = None
        self.updater = None
        self.name = name
        self.update_interval = 3
        self.telegraph_content = []
        self.path = []
        if not len(GFolder_ID) == 33 or not len(GFolder_ID) == 19:
            self.gparentid = self.getIdFromUrl(GFolder_ID)
        else:
            self.gparentid = GFolder_ID

    def cancel(self):
        self.is_cancelled = True
        self.is_uploading = False

    def speed(self):
        """
        It calculates the average upload speed and returns it in bytes/seconds unit
        :return: Upload speed in bytes/second
        """
        try:
            return self.uploaded_bytes / self.total_time
        except ZeroDivisionError:
            return 0

    @staticmethod
    def getIdFromUrl(link: str):
        if len(link) in [33, 19]:
            return link
        if "folders" in link or "file" in link:
            regex = r"https://drive\.google\.com/(drive)?/?u?/?\d?/?(mobile)?/?(file)?(folders)?/?d?/(?P<id>[-\w]+)[?+]?/?(w+)?"
            res = re.search(regex,link)
            if res is None:
                raise IndexError("❌ GDrive ID not found. ❌")
            return res.group('id')
        parsed = urlparse.urlparse(link)
        return parse_qs(parsed.query)['id'][0]

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(5),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def _on_upload_progress(self):
        if self.status is not None:
            chunk_size = self.status.total_size * self.status.progress() - self._file_uploaded_bytes
            self._file_uploaded_bytes = self.status.total_size * self.status.progress()
            LOGGER.debug(f'Uploading {self.name}, chunk size: {get_readable_file_size(chunk_size)}')
            self.uploaded_bytes += chunk_size
            self.total_time += self.update_interval

    def __upload_empty_file(self, path, file_name, mime_type, parent_id=None):
        media_body = MediaFileUpload(path,
                                     mimetype=mime_type,
                                     resumable=False)
        file_metadata = {
            'name': file_name,
            'description': 'mirror',
            'mimeType': mime_type,
        }
        if parent_id is not None:
            file_metadata['parents'] = [parent_id]
        return self.__service.files().create(supportsTeamDrives=True,
                                             body=file_metadata, media_body=media_body).execute()

    def switchServiceAccount(self):
        global SERVICE_ACCOUNT_INDEX
        service_account_count = len(os.listdir("accounts"))
        if SERVICE_ACCOUNT_INDEX == service_account_count - 1:
            SERVICE_ACCOUNT_INDEX = 0
        SERVICE_ACCOUNT_INDEX += 1
        LOGGER.info(f"Switching to {SERVICE_ACCOUNT_INDEX}.json service account")
        self.__service = self.authorize()

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(5),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def __set_permission(self, drive_id):
        permissions = {
            'role': 'reader',
            'type': 'anyone',
            'value': None,
            'withLink': True
        }
        return self.__service.permissions().create(supportsTeamDrives=True, fileId=drive_id,
                                                   body=permissions).execute()

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(5),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def upload_file(self, file_path, file_name, mime_type, parent_id):
        # File body description
        file_metadata = {
            'name': file_name,
            'description': 'mirror',
            'mimeType': mime_type,
        }
        if parent_id is not None:
            file_metadata['parents'] = [parent_id]

        if os.path.getsize(file_path) == 0:
            media_body = MediaFileUpload(file_path,
                                         mimetype=mime_type,
                                         resumable=False)
            response = self.__service.files().create(supportsTeamDrives=True,
                                                     body=file_metadata, media_body=media_body).execute()
            if not IS_TEAM_DRIVE:
                self.__set_permission(response['id'])

            drive_file = self.__service.files().get(supportsTeamDrives=True,
                                                    fileId=response['id']).execute()
            download_url = self.__G_DRIVE_BASE_DOWNLOAD_URL.format(drive_file.get('id'))
            return download_url
        media_body = MediaFileUpload(file_path,
                                     mimetype=mime_type,
                                     resumable=True,
                                     chunksize=50 * 1024 * 1024)

        # Insert a file
        drive_file = self.__service.files().create(supportsTeamDrives=True,
                                                   body=file_metadata, media_body=media_body)
        response = None
        while response is None:
            if self.is_cancelled:
                return None
            try:
                self.status, response = drive_file.next_chunk()
            except HttpError as err:
                if err.resp.get('content-type', '').startswith('application/json'):
                    reason = json.loads(err.content).get('error').get('errors')[0].get('reason')
                    if reason == 'userRateLimitExceeded' or reason == 'dailyLimitExceeded':
                        if USE_SERVICE_ACCOUNTS:
                            self.switchServiceAccount()
                            LOGGER.info(f"Got: {reason}, Trying Again.")
                            return self.upload_file(file_path, file_name, mime_type, parent_id)
                    else:
                        raise err
        self._file_uploaded_bytes = 0
        # Insert new permissions
        if not IS_TEAM_DRIVE:
            self.__set_permission(response['id'])
        # Define file instance and get url for download
        drive_file = self.__service.files().get(supportsTeamDrives=True, fileId=response['id']).execute()
        download_url = self.__G_DRIVE_BASE_DOWNLOAD_URL.format(drive_file.get('id'))
        return download_url

    def deletefile(self, link: str):
        try:
            file_id = self.getIdFromUrl(link)
        except (KeyError,IndexError):
            msg = "❌ Google drive ID could not be found in the provided link. ❌"
            return msg
        msg = ''
        try:
            res = self.__service.files().delete(fileId=file_id, supportsTeamDrives=IS_TEAM_DRIVE).execute()
            msg = "🚮 Successfully deleted"
        except HttpError as err:
            LOGGER.error(str(err))
            if "File not found" in str(err):
                msg = "❌ No such file exist ❌"
            else:
                msg = "❌ Something went wrong check log ❌"
        finally:
            return msg

    def upload(self, file_name: str):
        if USE_SERVICE_ACCOUNTS:
            self.service_account_count = len(os.listdir("accounts"))
        self.__listener.onUploadStarted()
        file_dir = f"{DOWNLOAD_DIR}{self.__listener.message.message_id}"
        file_path = f"{file_dir}/{file_name}"
        size = get_readable_file_size(get_path_size(file_path))
        LOGGER.info("Uploading File: " + file_path)
        self.start_time = time.time()
        self.updater = setInterval(self.update_interval, self._on_upload_progress)
        if os.path.isfile(file_path):
            try:
                mime_type = get_mime_type(file_path)
                link = self.upload_file(file_path, file_name, mime_type, parent_id)
                if link is None:
                    raise Exception('Upload has been manually cancelled')
                LOGGER.info("📤 Uploaded To G-Drive: " + file_path)
            except Exception as e:
                if isinstance(e, RetryError):
                    LOGGER.info(f"⚙️ Total Attempts: {e.last_attempt.attempt_number}")
                    err = e.last_attempt.exception()
                else:
                    err = e
                LOGGER.error(err)
                self.__listener.onUploadError(str(err))
                return
            finally:
                self.updater.cancel()
        else:
            try:
                dir_id = self.create_directory(os.path.basename(os.path.abspath(file_name)), parent_id)
                result = self.upload_dir(file_path, dir_id)
                if result is None:
                    raise Exception('Upload has been manually cancelled!')
                LOGGER.info("📤 Uploaded To G-Drive: " + file_name)
                link = f"https://drive.google.com/folderview?id={dir_id}"
            except Exception as e:
                if isinstance(e, RetryError):
                    LOGGER.info(f"⚙️ Total Attempts: {e.last_attempt.attempt_number}")
                    err = e.last_attempt.exception()
                else:
                    err = e
                LOGGER.error(err)
                self.__listener.onUploadError(str(err))
                return
            finally:
                self.updater.cancel()
        LOGGER.info(download_dict)
        self.__listener.onUploadComplete(link, size)
        LOGGER.info("Deleting downloaded file/folder..")
        return link

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(5),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def copyFile(self, file_id, dest_id):
        body = {
            'parents': [dest_id]
        }

        try:
            res = self.__service.files().copy(supportsAllDrives=True,fileId=file_id,body=body).execute()
            return res
        except HttpError as err:
            if err.resp.get('content-type', '').startswith('application/json'):
                reason = json.loads(err.content).get('error').get('errors')[0].get('reason')
                if reason == 'userRateLimitExceeded' or reason == 'dailyLimitExceeded':
                    if USE_SERVICE_ACCOUNTS:
                        self.switchServiceAccount()
                        LOGGER.info(f"⚙️ Bot Got: {reason}, Trying Again.")
                        return self.copyFile(file_id,dest_id)
                else:
                    raise err

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(5),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def getFileMetadata(self,file_id):
        return self.__service.files().get(supportsAllDrives=True, fileId=file_id,
                                              fields="name,id,mimeType,size").execute()

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(5),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def getFilesByFolderId(self,folder_id):
        page_token = None
        q = f"'{folder_id}' in parents"
        files = []
        while True:
            response = self.__service.files().list(supportsTeamDrives=True,
                                                   includeTeamDriveItems=True,
                                                   q=q,
                                                   spaces='drive',
                                                   pageSize=200,
                                                   fields='nextPageToken, files(id, name, mimeType,size)',
                                                   pageToken=page_token).execute()
            for file in response.get('files', []):
                files.append(file)
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
        return files

    def clone(self, link, status, ignoreList=[]):
        self.transferred_size = 0
        try:
            file_id = self.getIdFromUrl(link)
        except (KeyError,IndexError):
            msg = "❌ Google drive ID could not be found in the provided link ❌"
            return msg, ""
        msg = ""
        LOGGER.info(f"File ID: {file_id}")
        try:
            meta = self.getFileMetadata(file_id)
            dest_meta = self.getFileMetadata(file_id)
            
            status.SetMainFolder(meta.get('name'), self.__G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(meta.get('id')))
            status.SetDestinationFolder(dest_meta.get('name'), self.__G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(dest_meta.get('id')))
            
                if meta.get("mimeType") == self.__G_DRIVE_DIR_MIME_TYPE:
                dir_id = self.check_folder_exists(meta.get('name'), self.gparentid)
                    if not dir_id:
                        dir_id = self.create_directory(meta.get('name'), self.gparentid)
                result self.cloneFolder(meta.get('name'), meta.get('name'), meta.get('id'), dir_id, status, ignoreList)
            except Exception as e:
            if isinstance(e, RetryError):
                LOGGER.info(f"Total Attempts: {e.last_attempt.attempt_number}")
                err = e.last_attempt.exception()
            else:
                err = str(e).replace('>', '').replace('<', '')
            LOGGER.error(err)
            return err
            status.set_status(True)
            return msg, InlineKeyboardMarkup(buttons.build_menu(2))
                
                msg += f'<b>🔰 Name : </b><code>{meta.get("name")}</code>\n\n<b>🔰 Size : </b>{get_readable_file_size(self.transferred_size)}\n\n<i>👾 Join Our Team Drive To Access The G-Drive Link.</i>\n<i>👾 Do Not Share The Index Link In Public Groups/Channel/Forums Etc Without Permission.</i>\n<i>👾<b>Permanent Banned</b> if you break The Rules.</i>\n\n #Uploads @Jusidama'
                durl = self.__G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(dir_id)
                buttons = button_build.ButtonMaker()
                if SHORTENER is not None and SHORTENER_API is not None:
                    surl = requests.get('https://{}/api?api={}&url={}&format=text'.format(SHORTENER, SHORTENER_API, durl)).text
                    buttons.buildbutton("☁️G-Drive Link☁️", surl)
                else:
                    buttons.buildbutton("☁️G-Drive Link☁️", durl)
                if INDEX_URL is not None:
                    url = requests.utils.requote_uri(f'{INDEX_URL}/{meta.get("name")}/')
                    if SHORTENER is not None and SHORTENER_API is not None:
                        siurl = requests.get('https://{}/api?api={}&url={}&format=text'.format(SHORTENER, SHORTENER_API, url)).text
                        buttons.buildbutton("🔗G-Index Link🔗", siurl)
                    else:
                        buttons.buildbutton("🔗G-Index Link🔗", url)
                if BUTTON_THREE_NAME is not None and BUTTON_THREE_URL is not None:
                    buttons.buildbutton(f"{BUTTON_THREE_NAME}", f"{BUTTON_THREE_URL}")
                if BUTTON_FOUR_NAME is not None and BUTTON_FOUR_URL is not None:
                    buttons.buildbutton(f"{BUTTON_FOUR_NAME}", f"{BUTTON_FOUR_URL}")
                if BUTTON_FIVE_NAME is not None and BUTTON_FIVE_URL is not None:
                    buttons.buildbutton(f"{BUTTON_FIVE_NAME}", f"{BUTTON_FIVE_URL}")
            else:
                file = self.copyFile(meta.get('id'), parent_id)
                msg += f'<b>Filename : </b><code>{file.get("name")}</code>'
                durl = self.__G_DRIVE_BASE_DOWNLOAD_URL.format(file.get("id"))
                buttons = button_build.ButtonMaker()
                if SHORTENER is not None and SHORTENER_API is not None:
                    surl = requests.get('https://{}/api?api={}&url={}&format=text'.format(SHORTENER, SHORTENER_API, durl)).text
                    buttons.buildbutton("☁️G-Drive Link☁️", surl)
                else:
                    buttons.buildbutton("☁️G-Drive Link☁️", durl)
                try:
                    msg += f'\n<b>Size : </b><code>{get_readable_file_size(int(meta.get("size")))}</code>'
                except TypeError:
                    pass
                if INDEX_URL is not None:
                    url = requests.utils.requote_uri(f'{INDEX_URL}/{file.get("name")}')
                    if SHORTENER is not None and SHORTENER_API is not None:
                        siurl = requests.get('https://{}/api?api={}&url={}&format=text'.format(SHORTENER, SHORTENER_API, url)).text
                        buttons.buildbutton("🔗G-Index Link🔗", siurl)
                    else:
                        buttons.buildbutton("🔗G-Index Link🔗", url)
                if BUTTON_THREE_NAME is not None and BUTTON_THREE_URL is not None:
                    buttons.buildbutton(f"{BUTTON_THREE_NAME}", f"{BUTTON_THREE_URL}")
                if BUTTON_FOUR_NAME is not None and BUTTON_FOUR_URL is not None:
                    buttons.buildbutton(f"{BUTTON_FOUR_NAME}", f"{BUTTON_FOUR_URL}")
                if BUTTON_FIVE_NAME is not None and BUTTON_FIVE_URL is not None:
                    buttons.buildbutton(f"{BUTTON_FIVE_NAME}", f"{BUTTON_FIVE_URL}")

    def cloneFolder(self, name, local_path, folder_id, parent_id, status, ignoreList=[]):
        page_token = None
        q = f"'{folder_id}' in parents"
        files = []
        LOGGER.info(f"Syncing: {local_path}")
        while True:
            response = self.__service.files().list(supportsTeamDrives=True,
                                                   includeTeamDriveItems=True,
                                                   q=q,
                                                   spaces='drive',
                                                   fields='nextPageToken, files(id, name, mimeType,size)',
                                                   pageToken=page_token).execute()
            for file in response.get('files', []):
                files.append(file)
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
        if len(files) == 0:
            return parent_id
        for file in files:
            if file.get('mimeType') == self.__G_DRIVE_DIR_MIME_TYPE:
                file_path = os.path.join(local_path, file.get('name'))
                current_dir_id = self.check_folder_exists(file.get('name'), parent_id)
                if not current_dir_id:
                    current_dir_id = self.create_directory(file.get('name'), parent_id)
                if not str(file.get('id')) in ignoreList:
                    self.cloneFolder(file.get('name'), file_path, file.get('id'), current_dir_id, status, ignoreList)
                else:
                    LOGGER.info("Ignoring FolderID from clone: " + str(file.get('id')))
            else:
                try:
                    if not self.check_file_exists(file.get('name'), parent_id):
                        status.checkFileExist(False)
                        self.copyFile(file.get('id'), parent_id, status)
                        self.transferred_size += int(file.get('size'))
                        status.set_name(file.get('name'))
                        status.add_size(int(file.get('size')))
                    else:
                        status.checkFileExist(True)
                except TypeError:
                    pass
                except Exception as e:
                    if isinstance(e, RetryError):
                        LOGGER.info(f"Total Attempts: {e.last_attempt.attempt_number}")
                        err = e.last_attempt.exception()
                    else:
                        err = e
                    LOGGER.error(err)

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(5),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def create_directory(self, directory_name, parent_id):
        file_metadata = {
            "name": directory_name,
            "mimeType": self.__G_DRIVE_DIR_MIME_TYPE
        }
        if parent_id is not None:
            file_metadata["parents"] = [parent_id]
        file = self.__service.files().create(supportsTeamDrives=True, body=file_metadata).execute()
        file_id = file.get("id")
        if not IS_TEAM_DRIVE:
            self.__set_permission(file_id)
        LOGGER.info("✅ Created Google-Drive Folder:\nName: {}\nID: {} ".format(file.get("name"), file_id))
        return file_id

    def upload_dir(self, input_directory, parent_id):
        list_dirs = os.listdir(input_directory)
        if len(list_dirs) == 0:
            return parent_id
        new_id = None
        for item in list_dirs:
            current_file_name = os.path.join(input_directory, item)
            if self.is_cancelled:
                return None
            if os.path.isdir(current_file_name):
                current_dir_id = self.create_directory(item, parent_id)
                new_id = self.upload_dir(current_file_name, current_dir_id)
            else:
                mime_type = get_mime_type(current_file_name)
                file_name = current_file_name.split("/")[-1]
                # current_file_name will have the full path
                self.upload_file(current_file_name, file_name, mime_type, parent_id)
                new_id = parent_id
        return new_id

    def authorize(self):
        # Get credentials
        credentials = None
        if not USE_SERVICE_ACCOUNTS:
            if os.path.exists(self.__G_DRIVE_TOKEN_FILE):
                with open(self.__G_DRIVE_TOKEN_FILE, 'rb') as f:
                    credentials = pickle.load(f)
            if credentials is None or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', self.__OAUTH_SCOPE)
                    LOGGER.info(flow)
                    credentials = flow.run_console(port=0)

                # Save the credentials for the next run
                with open(self.__G_DRIVE_TOKEN_FILE, 'wb') as token:
                    pickle.dump(credentials, token)
        else:
            LOGGER.info(f"Authorizing with {SERVICE_ACCOUNT_INDEX}.json service account")
            credentials = service_account.Credentials.from_service_account_file(
                f'accounts/{SERVICE_ACCOUNT_INDEX}.json',
                scopes=self.__OAUTH_SCOPE)
        return build('drive', 'v3', credentials=credentials, cache_discovery=False)
    
    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def check_folder_exists(self, fileName, u_parent_id):
        fileName = clean_name(fileName)
        # Create Search Query for API request.
        query = f"'{u_parent_id}' in parents and (name contains '{fileName}' and trashed=false)"
        response = self.__service.files().list(supportsTeamDrives=True,
                                               includeTeamDriveItems=True,
                                               q=query,
                                               spaces='drive',
                                               pageSize=5,
                                               fields='files(id, name, mimeType, size)',
                                               orderBy='modifiedTime desc').execute()
        for file in response.get('files', []):
            if file.get('mimeType') == "application/vnd.google-apps.folder":  # Detect Whether Current Entity is a Folder or File.
                    driveid = file.get('id')
                    return driveid
    
    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(15),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def check_file_exists(self, fileName, u_parent_id):
        fileName = clean_name(fileName)
        # Create Search Query for API request.
        query = f"'{u_parent_id}' in parents and (name contains '{fileName}' and trashed=false)"
        response = self.__service.files().list(supportsTeamDrives=True,
                                               includeTeamDriveItems=True,
                                               q=query,
                                               spaces='drive',
                                               pageSize=5,
                                               fields='files(id, name, mimeType, size)',
                                               orderBy='modifiedTime desc').execute()
        for file in response.get('files', []):
            if file.get('mimeType') != "application/vnd.google-apps.folder":
                    # driveid = file.get('id')
                    return file


    def get_readable_file_size(size_in_bytes) -> str:
        SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        if size_in_bytes is None:
            return '0B'
        index = 0
        while size_in_bytes >= 1024:
            size_in_bytes /= 1024
            index += 1
        try:
            return f'{round(size_in_bytes, 2)}{SIZE_UNITS[index]}'
        except IndexError:
            return 'File too large'
                                                     
    def edit_telegraph(self):
        nxt_page = 1 
        prev_page = 0
        for content in self.telegraph_content :
            if nxt_page == 1 :
                content += f'<b><a href="https://telegra.ph/{self.path[nxt_page]}">Next</a></b>'
                nxt_page += 1
            else :
                if prev_page <= self.num_of_path:
                    content += f'<b><a href="https://telegra.ph/{self.path[prev_page]}">Prev</a></b>'
                    prev_page += 1
                if nxt_page < self.num_of_path:
                    content += f'<b> | <a href="https://telegra.ph/{self.path[nxt_page]}">Next</a></b>'
                    nxt_page += 1
            Telegraph(access_token=telegraph_token).edit_page(path = self.path[prev_page],
                                 title = 'John Torrent v.2.0 Bot Search',
                                 author_name='Jusidama',
                                 author_url='https://t.me/jusidama',
                                 html_content=content)
        return

    def escapes(self, str):
        chars = ['\\', "'", '"', r'\a', r'\b', r'\f', r'\n', r'\r', r'\t']
        for char in chars:
            str = str.replace(char, '\\'+char)
        return str

    def drive_list(self, fileName):
        msg = ""
        fileName = self.escapes(str(fileName))
        # Create Search Query for API request.
        query = f"'{parent_id}' in parents and (name contains '{fileName}')"
        response = self.__service.files().list(supportsTeamDrives=True,
                                               includeTeamDriveItems=True,
                                               q=query,
                                               spaces='drive',
                                               pageSize=200,
                                               fields='files(id, name, mimeType, size)',
                                               orderBy='modifiedTime desc').execute()

        content_count = 0
        if response["files"]:
            msg += f'<h4>Results : {fileName}</h4><br><br>'

            for file in response.get('files', []):
                if file.get('mimeType') == "application/vnd.google-apps.folder":  # Detect Whether Current Entity is a Folder or File.
                    furl = f"https://drive.google.com/drive/folders/{file.get('id')}"
                    msg += f"⁍<code>{file.get('name')}<br>(📁 Folder)</code><br>"
                    if SHORTENER is not None and SHORTENER_API is not None:
                        sfurl = requests.get('https://{}/api?api={}&url={}&format=text'.format(SHORTENER, SHORTENER_API, furl)).text
                        msg += f"<b><a href={sfurl}>☁️ Drive Link</a></b>"
                    else:
                        msg += f"<b><a href={furl}>☁️ Drive Link</a></b>"
                    if INDEX_URL is not None:
                        url = requests.utils.requote_uri(f'{INDEX_URL}/{file.get("name")}/')
                        if SHORTENER is not None and SHORTENER_API is not None:
                            siurl = requests.get('https://{}/api?api={}&url={}&format=text'.format(SHORTENER, SHORTENER_API, url)).text
                            msg += f' <b>| <a href="{siurl}">🔗 Index Link</a></b>'
                        else:
                            msg += f' <b>| <a href="{url}">🔗 Index Link</a></b>'
                else:
                    furl = f"https://drive.google.com/uc?id={file.get('id')}&export=download"
                    msg += f"⁍<code>{file.get('name')}<br>({get_readable_file_size(int(file.get('size')))})📄</code><br>"
                    if SHORTENER is not None and SHORTENER_API is not None:
                        sfurl = requests.get('https://{}/api?api={}&url={}&format=text'.format(SHORTENER, SHORTENER_API, furl)).text
                        msg += f"<b><a href={sfurl}>☁️ Drive Link</a></b>"
                    else:
                        msg += f"<b><a href={furl}>☁️ Drive Link</a></b>"
                    if INDEX_URL is not None:
                        url = requests.utils.requote_uri(f'{INDEX_URL}/{file.get("name")}')
                        if SHORTENER is not None and SHORTENER_API is not None:
                            siurl = requests.get('https://{}/api?api={}&url={}&format=text'.format(SHORTENER, SHORTENER_API, url)).text
                            msg += f' <b>| <a href="{siurl}">🔗 Index Link</a></b>'
                        else:
                            msg += f' <b>| <a href="{url}">🔗 Index Link</a></b>'
                msg += '<br><br>'
                content_count += 1
                if content_count == TELEGRAPHLIMIT :
                    self.telegraph_content.append(msg)
                    msg = ""
                    content_count = 0

            if msg != '':
                self.telegraph_content.append(msg)

            if len(self.telegraph_content) == 0:
                return "No result found.. 😞", None

            for content in self.telegraph_content :
                self.path.append(Telegraph(access_token=telegraph_token).create_page(
                                                        title = 'John Torrent v.2.0 Bot Search',
                                                        author_name='Jusidama',
                                                        author_url='https://t.me/jusidama',
                                                        html_content=content
                                                        )['path'])

            self.num_of_path = len(self.path)
            if self.num_of_path > 1:
                self.edit_telegraph()

            msg = f"<b>Search Results For {fileName} 👇🏻 </b>"
            buttons = button_build.ButtonMaker()   
            buttons.buildbutton("👉🏻 Click Here 👈🏻", f"https://telegra.ph/{self.path[0]}")

            return msg, InlineKeyboardMarkup(buttons.build_menu(1))

        else :
            return '', ''
