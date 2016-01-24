import csv
from collections import Counter, namedtuple
import os

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from django.contrib.redirects.models import Redirect
from html2text import html2text

import requests
try:
    # Use a cache, if installed, to make debugging the import quicker.
    import requests_cache
    requests_cache.install_cache('import_cache')
except ImportError:
    pass

from ....product.models import Category, Product, ProductImage


def import_products():
    file_name = os.path.join(os.path.dirname(__file__),
                             'highwire-export.csv')
    with open(file_name, mode='r') as infile:
        reader = csv.reader(infile)
        ProductTuple = namedtuple('product', next(reader))
        slug_counter = Counter()
        site = Site.objects.all()[0]

        for data in map(ProductTuple._make, reader):
            # FIXME? Product variations have duplicate slugs... but there
            # doesn't seem to be a decent way to get structured data out of
            # them. Revisit.
            slug_counter[data.handle] += 1
            if slug_counter[data.handle] > 1:
                continue

            product, created = Product.objects.get_or_create(
                name=data.title,
                description=html2text(data.description),
                price=data.price,
                weight=data.weight,
                available_on=None,
                updated_at=None,
            )

            if not created:
                continue

            image_urls = [url.strip() for url in data.images.split(',') if url]
            for index, url in enumerate(image_urls):
                product_image = ProductImage(
                    product=product,
                    alt=data.title,
                    order=index
                )
                # Download the image and set it on the instance.
                print('Downloading %s...' % url)
                image_content = ContentFile(requests.get(url).content)
                product_image.image.save(url.split('/')[-1], image_content)
                product_image.save()

            product.categories.add(*[int(pk) for pk in data.categories.split(',') if pk])
            #product.attributes.add(*[int(pk) for pk in data.categories.split(',') if pk])

            # Add redirects products URLs both with and without the
            # trailing slash.
            url = '/product/' + data.handle
            product_url = product.get_absolute_url()
            redirect, _created = Redirect.objects.get_or_create(
                site=site,
                old_path=url,
                new_path=product_url
            )
            redirect, _created = Redirect.objects.get_or_create(
                site=site,
                old_path=url + '/',
                new_path=product_url
            )


# class Product(models.Model, ItemRange):
#     name = models.CharField(
#         pgettext_lazy('Product field', 'name'), max_length=128)
#     description = models.TextField(
#         verbose_name=pgettext_lazy('Product field', 'description'))
#     categories = models.ManyToManyField(
#         Category, verbose_name=pgettext_lazy('Product field', 'categories'),
#         related_name='products')
#     price = PriceField(
#         pgettext_lazy('Product field', 'price'),
#         currency=settings.DEFAULT_CURRENCY, max_digits=12, decimal_places=2)
#     weight = WeightField(
#         pgettext_lazy('Product field', 'weight'), unit=settings.DEFAULT_WEIGHT,
#         max_digits=6, decimal_places=2)
#     available_on = models.DateField(
#         pgettext_lazy('Product field', 'available on'), blank=True, null=True)
#     attributes = models.ManyToManyField(
#         'ProductAttribute', related_name='products', blank=True)
#     updated_at = models.DateTimeField(
#         pgettext_lazy('Product field', 'updated at'), auto_now=True, null=True)


def import_categories():
    site = Site.objects.all()[0]
    file_name = os.path.join(os.path.dirname(__file__),
                             'highwire-categories.csv')
    with open(file_name, mode='r') as infile:
        reader = csv.reader(infile)
        CategoryTuple = namedtuple('category', next(reader))

        # Create categories, reusing the same primary keys as Highwire.
        for data in map(CategoryTuple._make, reader):
            category, _created = Category.objects.get_or_create(
                pk=int(data.id),
                name=data.name,
                slug=data.handle,
                description=html2text(data.description),
                parent_id=int(data.parentid) or None,
                hidden=False
            )
            # Add redirects products URLs both with and without the
            # trailing slash.
            url = '/products/' + data.handle
            category_url = category.get_absolute_url()
            redirect, _created = Redirect.objects.get_or_create(
                site=site,
                old_path=url,
                new_path=category_url
            )
            redirect, _created = Redirect.objects.get_or_create(
                site=site,
                old_path=url + '/',
                new_path=category_url
            )

        Category.tree.rebuild()


class Command(BaseCommand):
    help = 'Populate database with data from Google Shopping feed'

    def handle(self, *args, **options):
        import_categories()
        import_products()
