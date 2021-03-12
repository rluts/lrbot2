import logging
import os
import re
from datetime import datetime

from configs import WIKIS
from exceptions import *
from time import sleep

import pywikibot
import requests
from PIL import Image
from pywikibot import pagegenerators
from resizeimage import resizeimage
from resizeimage.imageexceptions import ImageSizeError
from sqlalchemy.orm import sessionmaker

from db import Upload, engine

logging.basicConfig(filename="error.log", level=logging.ERROR)


class Site:
    def __init__(self, *args):
        wiki, self.bot_config = args
        self.site = pywikibot.Site(*wiki.split('.'))

    def __getattr__(self, item):
        if item in ('bot_config', 'site'):
            return getattr(self, item)
        else:
            return getattr(self.site, item)

    def __get__(self, instance, owner):
        return instance.site


class ResizeBot:
    extensions = ('png', 'gif', 'jpg', 'jpeg', 'tiff', 'tif')
    path = 'tmp/'

    def __init__(self):
        self.sites = [Site(*item) for item in WIKIS.items()]
        Session = sessionmaker(bind=engine)
        self.session = Session()

    @staticmethod
    def get_transclude(template):
        pages = pagegenerators.ReferringPageGenerator(template, onlyTemplateInclusion=True)
        for page in pages:
            if isinstance(page, pywikibot.FilePage):
                yield page

    def run_resizing(self):
        for site in self.sites:
            template = pywikibot.Page(site.site, site.bot_config.template_name)
            pages = set(self.get_transclude(template))
            if not pages:
                print('No images found for {}.{}'.format(site.lang, site.family))
                continue
            for page in pages:
                try:
                    width, log = self.get_params(page, site)
                    self.check_file(page, width)
                    print(page.title())
                    user, revision = self.get_requester(page, site)
                    description = site.bot_config.edit_summary_process.format(user=user)
                    print(description)
                    log = ("\n== %s ==\n" % site.bot_config.log_section +
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
                    site.login()

                    try:
                        site.thank_revision(revision['revid'])
                    except Exception as ex:
                        logging.warning("Cannot thank: {}".format(ex))

                    self.upload(page, description)
                    comment = site.bot_config.message_success

                    if log:
                        comment += site.bot_config.upload_log_success
                        page.text += log
                except TemplateParamsError:
                    comment = site.bot_config.params_error
                except (DownloadError, OSError):
                    comment = site.bot_config.download_error
                except UploadError:
                    comment = site.bot_config.upload_error
                except ImageSizeError:
                    comment = site.bot_config.width_error
                except ImageFormatError:
                    comment = site.bot_config.format(formats=', '.join(self.extensions))
                except Exception as ex:
                    # comment = 'Unexpected error while file uploading: {}'.format(str(ex))
                    print(str(ex))
                    logging.error(str(ex))
                    continue

                page.text = self.remove_template(page.text, site)
                page.save(summary=comment, minor=True)

        print("Cleanup")
        self.purge_tmp()
        print("{} Sleeping 60 seconds".format(datetime.now()))
        sleep(60)
        self.run_resizing()

    def remove_template(self, wiki_text, site):
        for template in self.find_templates(wiki_text, site):
            print("Removing %s" % template)
            wiki_text = wiki_text.replace(template, '')

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

    def get_params(self, page, site):
        try:
            templates = page.templatesWithParams()

            params = next(filter(lambda x: x[0].title() == site.bot_config.template_name, templates), [])[1]
            width = int(params[0])
            log = True if 'log' in params else None
            return width, log
        except Exception as ex:
            raise TemplateParamsError(ex)

    def find_templates(self, wiki_text, site):
        return re.findall(site.bot_config.template_regex, wiki_text)

    def is_template_on_page(self, wiki_text, site):
        templates = self.find_templates(wiki_text, site)
        return bool(templates)

    def get_requester(self, page, site):
        user = 'unknown'
        last_revision = None
        for revision in page.revisions():
            wiki_text = page.getOldVersion(revision['revid'])
            if not self.is_template_on_page(wiki_text, site):
                break
            user = revision.user
            last_revision = revision
        return user, last_revision

    def purge_tmp(self):
        folder = self.path
        for the_file in os.listdir(folder):
            file_path = os.path.join(folder, the_file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                # elif os.path.isdir(file_path): shutil.rmtree(file_path)
            except Exception as ex:
                print(ex)


if __name__ == '__main__':
    while True:
        try:
            bot = ResizeBot()
            bot.run_resizing()
        except Exception as e:
            print(e)
            logging.error(e)
