from django import forms


class PlanDateForm(forms.Form):
    plan_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
