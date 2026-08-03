from django.dispatch import Signal


photo_published = Signal()
photo_unpublished = Signal()

channel_photo_published = Signal()
channel_photo_unpublished = Signal()
