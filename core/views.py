from django.urls import reverse
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django_tables2.views import SingleTableView
from django.db.models import Count
from .models import *
from .forms import *
from .tables import *
from .mixins import CRUDGenericMixin
from django.http import FileResponse, Http404
import calendar
from collections import defaultdict
import json

#region Photo

class PhotoMixin(CRUDGenericMixin):
    object_type_name = "Photo"
    object_type_name_plural = "Photos"
    object_url_name_slug = "photo"
    formset_support = True


class PhotoListView(PhotoMixin, SingleTableView):
    model = Photo
    table_class = PhotoTable
    template_name = "core/photo_list.html"

    paginate_by = 10


class PhotoDetailView(DetailView):
    model = Photo

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_sizes = Size.objects.all().order_by('max_dimension')
        photo_sizes = {ps.size_id: ps for ps in self.object.sizes.all()}
        context['sizes'] = [
            (size, photo_sizes.get(size.id)) for size in all_sizes
        ]
        context['custom_attributes'] = json.dumps(self.object.custom_attributes or {}, indent=2)
        return context


class PhotoImageView(DetailView):
    model = Photo

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        size = kwargs.get('size')
        try:
            image_file = self.object.get_size(size).image
        except (AttributeError, KeyError, FileNotFoundError):
            raise Http404("Requested size not found.")
        if not image_file or not hasattr(image_file, 'open'):
            raise Http404("Image not available.")
        return FileResponse(image_file.open('rb'), content_type='image/jpeg')


class PhotoCreateView(PhotoMixin, CreateView):
    model = Photo
    form_class = PhotoForm
    template_name = "core/photo_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add exclusion form to context
        try:
            from integration.forms import IntegrationPhotoForm
            if 'integration_photo_form' not in context:
                context['integration_photo_form'] = IntegrationPhotoForm(
                    self.request.POST if self.request.method == 'POST' else None,
                    photo_instance=None
                )
        except ImportError:
            pass
        return context

    def form_valid(self, form):
        # Get exclusion form
        integration_photo_form = None
        try:
            from integration.forms import IntegrationPhotoForm
            integration_photo_form = IntegrationPhotoForm(
                self.request.POST,
                photo_instance=None
            )
            if not integration_photo_form.is_valid():
                # Pass the exclusion form with errors back to the template
                context = self.get_context_data(form=form)
                context['integration_photo_form'] = integration_photo_form
                return self.render_to_response(context)
        except ImportError:
            pass
        
        # Save with exclusion form
        self.object = form.save(commit=True, integration_photo_form=integration_photo_form)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('photo-detail', kwargs={'pk': self.object.pk})


class PhotoCreateMultipleView(PhotoMixin, View):
    template_name = "core/photo_formset.html"

    def get(self, request, *args, **kwargs):
        formset = PhotoFormSet(queryset=Photo.objects.none())  # empty forms
        return render(request, self.template_name, {"formset": formset})

    def post(self, request, *args, **kwargs):
        formset = PhotoFormSet(request.POST, request.FILES, queryset=Photo.objects.none())
        if formset.is_valid():
            formset.save()
            return redirect(reverse("photo-list"))
        return render(request, self.template_name, {"formset": formset})


class PhotoCalendarView(TemplateView):
    template_name = "core/photo_calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()

        # Parse month/year from GET params
        req = self.request
        try:
            year = int(req.GET.get("year", today.year))
            month = int(req.GET.get("month", today.month))
        except ValueError:
            year, month = today.year, today.month

        # Calendar starting on Sunday
        cal = calendar.Calendar(firstweekday=6)
        month_dates = list(cal.itermonthdates(year, month))
        # Build contiguous weeks (list of 7-date lists)
        weeks_raw = [month_dates[i : i + 7] for i in range(0, len(month_dates), 7)]

        # Preload photos that fall within the displayed range
        range_start = month_dates[0]
        range_end = month_dates[-1]
        photos_qs = (
            Photo.objects.filter(publish_date__date__range=(range_start, range_end))
            .order_by('publish_date')
        )

        # Group photos by local date
        photos_map = defaultdict(list)
        for p in photos_qs:
            try:
                pd = timezone.localtime(p.publish_date).date()
            except Exception:
                # Fallback to naive date if timezone conversion fails
                pd = p.publish_date.date()
            photos_map[pd].append(p)

        # Build week/days data structure for template convenience
        weeks = []
        for week in weeks_raw:
            week_row = []
            for d in week:
                week_row.append({
                    'date': d,
                    'day': d.day,
                    'in_month': d.month == month,
                    'is_today': d == today,
                    'photos': photos_map.get(d, []),
                })
            weeks.append(week_row)

        # Prev/next month calculation
        if month == 1:
            prev_month, prev_year = 12, year - 1
        else:
            prev_month, prev_year = month - 1, year
        if month == 12:
            next_month, next_year = 1, year + 1
        else:
            next_month, next_year = month + 1, year

        # Years dropdown population from photo publish dates
        years_qs = Photo.objects.dates('publish_date', 'year')
        years = sorted({d.year for d in years_qs})
        if not years:
            years = [today.year]

        context.update(
            {
                'weeks': weeks,
                'month': month,
                'year': year,
                'month_name': calendar.month_name[month],
                'prev_month': prev_month,
                'prev_year': prev_year,
                'next_month': next_month,
                'next_year': next_year,
                'years': years,
                'weekdays': ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],
                'today': today,
            }
        )
        return context

class PhotoUpdateView(PhotoMixin, UpdateView):
    model = Photo
    form_class = PhotoForm
    template_name = "core/photo_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add exclusion form to context
        try:
            from integration.forms import IntegrationPhotoForm
            if 'integration_photo_form' not in context:
                context['integration_photo_form'] = IntegrationPhotoForm(
                    self.request.POST if self.request.method == 'POST' else None,
                    photo_instance=self.object
                )
        except ImportError:
            pass
        return context

    def form_valid(self, form):
        # Get exclusion form
        integration_photo_form = None
        try:
            from integration.forms import IntegrationPhotoForm
            integration_photo_form = IntegrationPhotoForm(
                self.request.POST,
                photo_instance=self.object
            )
            if not integration_photo_form.is_valid():
                # Pass the exclusion form with errors back to the template
                context = self.get_context_data(form=form)
                context['integration_photo_form'] = integration_photo_form
                return self.render_to_response(context)
        except ImportError:
            pass
        
        # Save with exclusion form
        self.object = form.save(commit=True, integration_photo_form=integration_photo_form)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('photo-detail', kwargs={'pk': self.object.pk})


class PhotoDeleteView(DeleteView):
    model = Photo
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('photo-list')

#endregion

#region Sizes


class SizeMixin(CRUDGenericMixin):
    object_type_name = "Size"
    object_type_name_plural = "Sizes"
    object_url_name_slug = "size"
    no_object_detail_page = True  # Sizes do not have a detail page
    edit_disclaimer = "Creating or modifying any size will trigger a reprocessing of all photos that use this size. This may take some time depending on the number of photos and sizes involved."


class SizeListView(SizeMixin, SingleTableView):
    model = Size
    template_name = "generic_crud_list.html"
    table_class = SizeTable  # No table for sizes yet


class SizeCreateView(SizeMixin, CreateView):
    model = Size
    form_class = SizeForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('size-list')


class SizeUpdateView(SizeMixin, UpdateView):
    model = Size
    form_class = SizeForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('size-list')


class SizeDeleteView(SizeMixin, DeleteView):
    model = Size
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('size-list')


#endregion

#region Albums


class AlbumMixin(CRUDGenericMixin):
    object_type_name = "Album"
    object_type_name_plural = "Albums"
    object_url_name_slug = "album"


class AlbumDetailView(DetailView):
    model = Album

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        ordered_photos = self.object.get_ordered_photos()
        table = PhotoListTable(ordered_photos)
        context["photo_table"] = table
        context['custom_attributes'] = json.dumps(self.object.custom_attributes or {}, indent=2)
        return context


class AlbumListView(AlbumMixin, TemplateView):
    template_name = "core/album_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Build a parent->children mapping for all albums, sorted alphabetically
        all_albums = Album.objects.all().order_by('title')
        children_map = {}
        for a in all_albums:
            parent_id = a.parent_id
            children_map.setdefault(parent_id, []).append(a)

        def build_nodes(parent_id=None):
            nodes = []
            for a in children_map.get(parent_id, []):
                nodes.append({
                    'album': a,
                    'children': build_nodes(a.id)
                })
            return nodes

        context['album_tree'] = build_nodes(None)
        return context


class AlbumCreateView(AlbumMixin, CreateView):
    model = Album
    form_class = AlbumForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('album-detail', kwargs={'pk': self.object.pk})


class AlbumUpdateView(AlbumMixin, UpdateView):
    model = Album
    form_class = AlbumForm
    template_name = "core/album_form.html"

    def form_valid(self, form):
        # Save the Album itself first
        response = super().form_valid(form)

        # Update photo order from submitted hidden inputs
        photo_ids = [int(pid) for pid in self.request.POST.getlist("photo_order[]") if pid]
        for idx, photo_id in enumerate(photo_ids, start=1):
            PhotoInAlbum.objects.filter(album=self.object, photo_id=photo_id).update(order=idx)


        return response

    def get_success_url(self):
        return reverse('album-detail', kwargs={'pk': self.object.pk})


class AlbumDeleteView(AlbumMixin, DeleteView):
    model = Album
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('album-list')

#endregion

#region Tags

class TagMixin(CRUDGenericMixin):
    object_type_name = "Tag"
    object_type_name_plural = "Tags"
    object_url_name_slug = "tag"
    edit_disclaimer = "Renaming a tag will update all photos that use this tag. Deleting a tag will remove it from all photos."
    can_directly_create = False  # Tags are managed through the photo form, not directly


class TagListView(TagMixin, SingleTableView):
    model = Tag
    template_name = "generic_crud_list.html"
    table_class = TagTable

    def get_queryset(self):
        return Tag.objects.annotate(photo_count=Count("photos"))


class TagDetailView(DetailView):
    model = Tag

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        photos = Photo.objects.filter(tags=self.object).distinct()

        table = PhotoListTable(photos)

        context["photo_table"] = table
        return context


class TagUpdateView(TagMixin, UpdateView):
    model = Tag
    form_class = TagForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        # If the tag was merged (and deleted), redirect to tag list
        if not Tag.objects.filter(pk=self.object.pk).exists():
            return reverse('tag-list')
        return reverse('tag-detail', kwargs={'pk': self.object.pk})


class TagDeleteView(TagMixin, DeleteView):
    model = Tag
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('tag-list')

#endregion