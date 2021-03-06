'''
Adapted from
https://github.com/divio/aldryn-search/blob/master/aldryn_search/search_indexes.py
'''

from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from django.template import Context
from django.utils.html import strip_tags

from django_elasticsearch_dsl import DocType, fields

from cms.models import Title

from froide.helper.search import (
    get_index, get_text_analyzer
)

from .utils import (
    render_placeholder, clean_join, get_request
)


index = get_index('cmspage')

analyzer = get_text_analyzer()


@index.doc_type
class CMSDocument(DocType):
    title = fields.TextField(
        fields={'raw': fields.KeywordField()},
        analyzer=analyzer,
    )
    url = fields.TextField(
        fields={'raw': fields.KeywordField()},
        analyzer=analyzer,
    )
    description = fields.TextField(
        fields={'raw': fields.KeywordField()},
        analyzer=analyzer,
    )

    content = fields.TextField(
        analyzer=analyzer
    )

    special_signals = True

    class Meta:
        model = Title
        queryset_chunk_size = 100

    def get_queryset(self):
        now = timezone.now()
        queryset = Title.objects.public().filter(
            Q(page__publication_date__lt=now) | Q(page__publication_date__isnull=True),
            Q(page__publication_end_date__gte=now) | Q(page__publication_end_date__isnull=True),
            Q(redirect__exact='') | Q(redirect__isnull=True),
            language=settings.LANGUAGE_CODE
        ).select_related('page')

        queryset = queryset.select_related('page__node')
        return queryset.distinct()

    def prepare_content(self, obj):
        current_language = settings.LANGUAGE_CODE
        request = get_request(current_language)
        content = self.get_search_data(obj, current_language, request)
        return content

    def prepare_description(self, obj):
        return obj.meta_description or ''

    def prepare_url(self, obj):
        return obj.page.get_absolute_url()

    def prepare_title(self, obj):
        return obj.title

    def get_page_placeholders(self, page):
        """
        In the project settings set up the variable
        PLACEHOLDERS_SEARCH_LIST = {
            # '*' is mandatory if you define at least one slot rule
            '*': {
                'include': [ 'slot1', 'slot2', etc. ],
                'exclude': [ 'slot3', 'slot4', etc. ],
            }
            'reverse_id_alpha': {
                'include': [ 'slot1', 'slot2', etc. ],
                'exclude': [ 'slot3', 'slot4', etc. ],
            },
            'reverse_id_beta': {
                'include': [ 'slot1', 'slot2', etc. ],
                'exclude': [ 'slot3', 'slot4', etc. ],
            },
            'reverse_id_only_include': {
                'include': [ 'slot1', 'slot2', etc. ],
            },
            'reverse_id_only_exclude': {
                'exclude': [ 'slot3', 'slot4', etc. ],
            },
            # exclude it from the placehoders search list
            # (however better to remove at all to exclude it)
            'reverse_id_empty': []
            etc.
        }
        or leave it empty
        PLACEHOLDERS_SEARCH_LIST = {}
        """
        reverse_id = page.reverse_id
        args = []
        kwargs = {}

        placeholders_by_page = getattr(settings, 'PLACEHOLDERS_SEARCH_LIST', {})

        if placeholders_by_page:
            filter_target = None
            excluded = []
            slots = []
            if '*' in placeholders_by_page:
                filter_target = '*'
            if reverse_id and reverse_id in placeholders_by_page:
                filter_target = reverse_id
            if not filter_target:
                raise AttributeError('Leave PLACEHOLDERS_SEARCH_LIST empty or set up at least the generic handling')
            if 'include' in placeholders_by_page[filter_target]:
                slots = placeholders_by_page[filter_target]['include']
            if 'exclude' in placeholders_by_page[filter_target]:
                excluded = placeholders_by_page[filter_target]['exclude']
            diff = set(slots) - set(excluded)
            if diff:
                kwargs['slot__in'] = diff
            else:
                args.append(~Q(slot__in=excluded))
        return page.placeholders.filter(*args, **kwargs)

    def get_search_data(self, obj, language, request):
        current_page = obj.page

        text_bits = []
        context = Context({
            'request': get_request()
        })
        placeholders = self.get_page_placeholders(current_page)
        for placeholder in placeholders:
            text_bits.append(
                strip_tags(render_placeholder(context, placeholder))
            )

        page_meta_description = current_page.get_meta_description(fallback=False, language=language)

        if page_meta_description:
            text_bits.append(page_meta_description)

        page_meta_keywords = getattr(current_page, 'get_meta_keywords', None)

        if callable(page_meta_keywords):
            text_bits.append(page_meta_keywords())

        return clean_join(' ', text_bits)
