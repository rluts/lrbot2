# -*- coding: utf-8 -*-

import pywikibot
from pywikibot import pagegenerators
import requests
from PIL import Image
from resizeimage import resizeimage
from exceptions import *
from datetime import datetime
import re
import logging
from resizeimage.imageexceptions import ImageSizeError
from time import sleep
import os

from sqlalchemy.orm import sessionmaker

from db import engine, Upload

logging.basicConfig(filename="error.log", level=logging.ERROR)


class ResizeBot:
    template_name = 'Користувач:LRBot/resize'
    template_regex = '\\{\\{\\s?(?:User|Користувач)?:LRBot/resize\\s?(?:\\|.+|\\s.+}})'
    description = "Зменшення розміру зображення за запитом користувача [[User:{user}|{user}]]"
    log_section = 'Журнал завантажень'
    extensions = ('png', 'gif', 'jpg', 'jpeg', 'tiff', 'tif')
    path = 'tmp/'

    messages = {
        'success': 'Зображення зменшено',
        'log': '. Доданий журнал завантажень'
    }

    errors = {
        'templateparamserror': 'Помилка при завантаженні параметрів шаблону. '
                               '[[User:LRBot/resize|Дивіться документацію]].',
        'downloaderror': 'Неможливо завантажити зображення з сервера',
        'uploaderror': 'Неможливо завантажити зображення на сервер',
        'imagesizeerror': 'Вкажіть ширину файлу, меншу за поточну',
        'imageformaterror': 'Формат не підтримується. Доступні формати: {}'
    }

    def __init__(self):
        self.site = pywikibot.Site()
        self.template = pywikibot.Page(self.site, self.template_name)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def get_transclude(self):
        pages = pagegenerators.ReferringPageGenerator(self.template, onlyTemplateInclusion=True)
        for page in pages:
            if isinstance(page, pywikibot.FilePage):
                yield page

    def run_resizing(self):
        pages = set(self.get_transclude())
        if not pages:
            print("Cleanup")
            self.purge_tmp()
            print("{} Sleeping 60 seconds".format(datetime.now()))
            sleep(60)
            self.run_resizing()
        for page in pages:
            try:
                width, log = self.get_params(page)
                self.check_file(page, width)
                print(page.title())
                user, revision = self.get_requester(page)
                description = self.description.format(user=user)
                print(description)
                log = ("\n== %s ==\n{|class=\"wikitable\"\n" % self.log_section +
                       page.getFileVersionHistoryTable()) if log else None

                db_instance = Upload(
                    datetime=datetime.now(),
                    username=user,
                    width=width,
                    filename=page.title(),
                    status=0,
                    log=bool(log)
                )
                self.session.add(db_instance)
                self.session.commit()

                self.get_image(page)
                self.resize_img(page, width)
                self.site.login()
                try:
                    revision._thank(revision['revid'], self.site)
                except Exception as e:
                    pass

                self.upload(page, description)
                comment = self.messages['success']

                if log:
                    comment += self.messages['log']
                    page.text += log
            except TemplateParamsError:
                comment = self.errors['templateparamserror']
            except (DownloadError, OSError):
                comment = self.errors['downloaderror']
            except UploadError:
                comment = self.errors['uploaderror']
            except ImageSizeError:
                comment = self.errors['imagesizeerror']
            except ImageFormatError:
                comment = self.errors['imageformaterror'].format(', '.join(self.extensions))
            except Exception as ex:
                logging.error(ex)
                continue
            page.text = self.remove_template(page.text)
            page.save(summary=comment, minor=True)

    def remove_template(self, wiki_text):
        for template in self._find_templates(wiki_text):
            print("Removing %s" % template)
            wiki_text = wiki_text.replace(template, '')
        # print(wiki_text)
        return wiki_text

    def upload(self, page, description):
        upload = page.upload(self.get_thumb_filename(page), comment=description, report_success=True,
                             ignore_warnings=True)
        if not upload:
            raise UploadError

    def check_file(self, page, width):
        try:
            ext = page.title().split('.')[-1].lower()
            if ext not in self.extensions:
                raise ValueError
        except Exception as ex:
            raise ImageFormatError(ex)
        try:
            info = page.latest_file_info
        except Exception as ex:
            raise ImageFormatError(ex)
        current_width = info.width
        if current_width <= width:
            print(current_width, width)
            raise ImageSizeError(actual_size=width, required_size=current_width)

    def get_image(self, page):
        url = page.get_file_url()
        r = requests.get(url, stream=True)
        if r.status_code == 200:
            filename = self.get_file_name(page)
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            return filename
        else:
            raise DownloadError

    def get_file_name(self, page, with_path=True):
        path = self.path if with_path else ''
        return path + page.title(with_ns=False, as_filename=True)

    def get_thumb_filename(self, page):
        tmp = self.get_file_name(page).split('.')
        tmp[-2] += '_thumb'
        return '.'.join(tmp)

    def resize_img(self, page, width):
        with open(self.get_file_name(page),  'rb') as f:
            img = Image.open(f)
            img = resizeimage.resize_width(img, width)
            new_image_name = self.get_thumb_filename(page)
            img.save(new_image_name, img.format)

    def get_params(self, page):
        try:
            templates = page.templatesWithParams()
            params = dict(templates).get(self.template)
            width = int(params[0])
            log = True if 'log' in params else None
            return width, log
        except Exception as ex:
            raise TemplateParamsError(ex)

    def _find_templates(self, wiki_text):
        return re.findall(self.template_regex, wiki_text)

    def _is_template_on_page(self, wiki_text):
        templates = self._find_templates(wiki_text)
        return bool(templates)

    def get_requester(self, page):
        user = 'unknown'
        last_revision = None
        for revision in page.revisions():
            wiki_text = page.getOldVersion(revision['revid'])
            if not self._is_template_on_page(wiki_text):
                return user, last_revision
            user = revision.user
            last_revision = revision

    def purge_tmp(self):
        folder = self.path
        for the_file in os.listdir(folder):
            file_path = os.path.join(folder, the_file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                # elif os.path.isdir(file_path): shutil.rmtree(file_path)
            except Exception as e:
                print(e)


if __name__ == '__main__':
    while True:
        try:
            bot = ResizeBot()
            bot.run_resizing()
        except Exception as e:
            print(e)
            logging.error(e)
