from django import forms
from django.contrib.gis.forms import PointField, PolygonField, OSMWidget

from discoverer.models import DatasetOutput

FILETYPE_CSV = 'csv'
FILETYPE_KML = 'kml'
FILETYPE_CHOICES = (
    (FILETYPE_KML, 'KML'),
    (FILETYPE_CSV, 'CSV'),
)


class OregonWidget(OSMWidget):
    default_lon = -120
    default_lat = 44
    default_zoom = 1


class Html5DateInput(forms.DateInput):
    input_type = 'date'


class ExportDatasetForm(forms.ModelForm):
    discovered_after = forms.DateField(widget=Html5DateInput(), required=False, help_text='(oldest: 07/19/2016)')
    filetype = forms.ChoiceField(choices=FILETYPE_CHOICES)

    csv_delimiter = forms.CharField(required=False, help_text='A one-character string used to separate fields.')
    csv_quotechar = forms.CharField(required=False, help_text='A one-character string used to quote fields containing special characters, such as the delimiter or quotechar, or which contain new-line characters.')
    csv_lineterminator = forms.CharField(required=False, help_text='The string used to terminate lines.')
    csv_doublequote = forms.ChoiceField(choices=((True, "double the character"), (False, "use escapechar as a prefix to quotechar")), help_text='Controls how instances of quotechar appearing inside a field should themselves be quoted.')
    csv_escapechar = forms.CharField(required=False, help_text='A one-character string used to escape the delimiter.')

    range = PolygonField(widget=OregonWidget())

    class Meta:
        model = DatasetOutput
        fields = ('name',)

    def get_csv_formatting_kwargs(self, data=None):
        if data is None:
            data = self.data

        kwargs = {
            'delimiter': data.get('csv_delimiter').decode('unicode_escape').encode('utf-8'),
            'quotechar': data.get('csv_quotechar').decode('unicode_escape').encode('utf-8'),
            'lineterminator': data.get('csv_lineterminator').decode('unicode_escape').encode('utf-8'),
            'escapechar': data.get('csv_escapechar').decode('unicode_escape').encode('utf-8'),
            'doublequote': data.get('csv_doublequote').encode('utf-8'),
        }
        return kwargs
