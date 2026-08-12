"""
admin_skills.py - Skill-Formular für Consultant Admin
Ermöglicht die Bearbeitung der 28 Skill-Kategorien im Admin
"""

from django import forms
from django.contrib import admin
from django.utils.html import format_html
from . import models

# 28 Skill-Kategorien mit deutschen Namen
SKILL_CATEGORIES = [
    ('programming_languages', 'Programmiersprachen'),
    ('framework', 'Frameworks'),
    ('database', 'Datenbanken'),
    ('operating_system', 'Betriebssysteme'),
    ('cloud_platform', 'Cloud Plattformen'),
    ('devops_tool', 'DevOps Tools'),
    ('it_infrastructure', 'IT Infrastruktur'),
    ('security_tool', 'Security Tools'),
    ('network_protocol', 'Netzwerkprotokolle'),
    ('hardware', 'Hardware'),
    ('virtualization', 'Virtualisierung'),
    ('development_environment', 'Entwicklungsumgebungen'),
    ('version_control', 'Versionsverwaltung'),
    ('architecture_pattern', 'Architekturmuster'),
    ('data_format', 'Datenformate'),
    ('ci_cd_tool', 'CI/CD Tools'),
    ('testing_tool', 'Testing Tools'),
    ('monitoring_tool', 'Monitoring Tools'),
    ('identity_management', 'Identity Management'),
    ('data_management', 'Datenmanagement'),
    ('project_management', 'Projektmanagement'),
    ('communication_tool', 'Kommunikationstools'),
    ('documentation_tool', 'Dokumentationstools'),
    ('business_software', 'Business Software'),
    ('methodology', 'Methoden'),
    ('soft_skill', 'Soft Skills'),
    ('special_concept', 'Spezielle Konzepte'),
    ('other', 'Sonstige'),
]

class SkillForm(forms.Form):
    """Formular für eine Skill-Kategorie"""
    skills = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'cols': 80, 'style': 'width: 100%;'}),
        required=False,
        help_text="Kommagetrennte Liste, z.B. 'Python, Java, C++'"
    )

def create_skill_inline():
    """Erstellt ein Inline-Formular für alle 28 Kategorien"""
    
    class DynamicSkillsInline(admin.TabularInline):
        model = models.Consultant
        extra = 0
        can_delete = False
        verbose_name = "Skills (28 Kategorien)"
        verbose_name_plural = "Skills (28 Kategorien)"
        
        def get_formset(self, request, obj=None, **kwargs):
            # Dynamische Felder für jede Kategorie erstellen
            fields = []
            for cat_key, cat_name in SKILL_CATEGORIES:
                fields.append((cat_key, forms.CharField(
                    label=cat_name,
                    widget=forms.Textarea(attrs={'rows': 3, 'cols': 80}),
                    required=False,
                    help_text=f"Kommagetrennte Liste für {cat_name}"
                )))
            
            # Formset erstellen
            from django.forms import formset_factory
            from django.forms.models import modelform_factory
            
            return super().get_formset(request, obj, **kwargs)
        
        def get_fields(self, request, obj=None):
            return [cat_key for cat_key, _ in SKILL_CATEGORIES]
    
    return DynamicSkillsInline

# Füge das Inline zum ConsultantAdmin hinzu (wird später gemacht)
def patch_consultant_admin():
    """Fügt die Skill-Inlines zum ConsultantAdmin hinzu"""
    from django.contrib import admin
    from . import admin as cv_admin
    
    # Hole die existing ConsultantAdmin Klasse
    ConsultantAdmin = cv_admin.ConsultantAdmin
    
    # Füge Inline hinzu
    if not hasattr(ConsultantAdmin, 'inlines'):
        ConsultantAdmin.inlines = []
    
    # Erstelle Inline-Klasse
    class SkillsInline(admin.TabularInline):
        model = models.Consultant
        extra = 0
        can_delete = False
        verbose_name = "Skills (28 Kategorien)"
        verbose_name_plural = "Skills (28 Kategorien)"
        
        def get_formset(self, request, obj=None, **kwargs):
            # Dynamische Felder
            class SkillFormSet(forms.BaseInlineFormSet):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    if obj and obj.extracted_json_export:
                        skills = obj.extracted_json_export.get('extracted_data', {}).get('skills', {})
                        for form in self.forms:
                            for cat_key, _ in SKILL_CATEGORIES:
                                if cat_key in form.fields:
                                    value = skills.get(cat_key, [])
                                    form.fields[cat_key].initial = ', '.join(value)
            
            formset = super().get_formset(request, obj, **kwargs)
            formset.formset = SkillFormSet
            return formset
        
        def get_fields(self, request, obj=None):
            return [cat_key for cat_key, _ in SKILL_CATEGORIES]
    
    ConsultantAdmin.inlines.append(SkillsInline)
    print("✅ Skills Inline zu ConsultantAdmin hinzugefügt")

# Führe die Änderung aus, wenn das Modul geladen wird
try:
    patch_consultant_admin()
except Exception as e:
    print(f"⚠️ Konnte ConsultantAdmin nicht patchen: {e}")
