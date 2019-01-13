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

from sqlalchemy.orm import sessionmaker

from db import engine, Upload

logging.basicConfig(filename="error.log", level=logging.ERROR)


class ResizeBot:
    template_name = 'Користувач:LRBot/resize'
    template_regex = '\\{\\{\\s?(?:User|Користувач)?:LRBot/resize\\s?(?:\\|.+|\\s.+}})'
    description = "Зменшення розміру зображення за запитом користувача [[User:{user}|{user}]]"
    path = 'tmp/'
    locale_file = 'Файл:'

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
        pages = self.get_transclude()
        if not pages:
            sleep(60)
            self.run_resizing()
        for page in pages:
            try:
                params = self.get_params(page)
                width = params[0]
                print(page.title())
                user, revision = self.get_requester(page)
                description = self.description.format(user=user)
                print(description)
                log = page.getFileVersionHistoryTable() if 'log' in params else None
                print(log)  # TODO:

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
                try:
                    self.resize_img(page, int(width))
                    self.site.login()
                    try:
                        revision._thank(revision['revid'], self.site)
                    except Exception as e:
                        pass

                    self.upload(page, description)  # TODO: add try except

                except (OSError, ImageSizeError):  # TODO: resizeimage.imageexceptions.ImageSizeError
                    continue

            except (TemplateParamsError, DownloadError, ValueError):
                continue

    def upload(self, page, description):
        return page.upload(self.get_thumb_filename(page), comment=description, report_success=True,
                           ignore_warnings=True)

    def get_image(self, page):
        # TODO: page.download
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
        return path + page.title().replace(self.locale_file, '').replace(' ', '_')

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
        templates = page.templatesWithParams()
        params = dict(templates).get(self.template)
        if not params:
            raise TemplateParamsError
        return params

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


if __name__ == '__main__':
    # while True:
        # try:
            bot = ResizeBot()
            bot.run_resizing()
        # except Exception as e:
        #     print(e)
        #     logging.error(e)
