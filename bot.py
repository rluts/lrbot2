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

from sqlalchemy.orm import sessionmaker

from db import engine, Upload

logging.basicConfig(filename="error.log", level=logging.ERROR)


class ResizeBot:
    template_name = 'Користувач:LRBot/resize'
    template_regex = '\\{\\{\\s?(?:User|Користувач)?:LRBot/resize\\s?(?:\\||\\s}})'
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
        for page in self.get_transclude():
            try:
                params = self.get_params(page)
                width = params[0]
                print(page.title())
                user = self.get_requester(page)
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
                except (OSError, ImageSizeError):  # TODO: resizeimage.imageexceptions.ImageSizeError
                    continue

            except (TemplateParamsError, DownloadError, ValueError):
                continue

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

    def resize_img(self, page, width):
        with open(self.get_file_name(page),  'rb') as f:
            img = Image.open(f)
            img = resizeimage.resize_width(img, width)
            tmp = self.get_file_name(page).split('.')
            tmp[-2] += '_thumb'
            new_image_name = '.'.join(tmp)
            img.save(new_image_name, img.format)

    def get_params(self, page):
        templates = page.templatesWithParams()
        params = dict(templates).get(self.template)
        if not params:
            raise TemplateParamsError
        return params

    def _is_template_on_page(self, wiki_text):
        # print(re.findall(self.template_regex, wiki_text))
        return bool(re.findall(self.template_regex, wiki_text))

    def get_requester(self, page):
        user = 'unknown'
        for revision in page.revisions():
            wiki_text = page.getOldVersion(revision['revid'])
            if not self._is_template_on_page(wiki_text):
                return user
            user = revision.user


if __name__ == '__main__':
    # while True:
        # try:
            bot = ResizeBot()
            bot.run_resizing()
        # except Exception as e:
        #     print(e)
        #     logging.error(e)
