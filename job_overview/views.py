from .tables import TaskResultTable
from django_celery_results.models import TaskResult
from photoserv.mixins import CRUDGenericMixin
from django_tables2.views import SingleTableView


class JobMixin(CRUDGenericMixin):
    object_type_name = "Job"
    object_type_name_plural = "Jobs"
    object_url_name_slug = "job"
    can_directly_create = False
    no_object_detail_page = True


class JobListView(JobMixin, SingleTableView):
    model = TaskResult
    table_class = TaskResultTable
    template_name = "generic_crud_list.html"
