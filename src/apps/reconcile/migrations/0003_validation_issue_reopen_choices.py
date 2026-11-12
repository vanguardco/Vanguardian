from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("reconcile", "0002_validation_run_file_import_source")]

    operations = [
        migrations.AlterField(
            model_name="reconcilevalidationissuesnapshot",
            name="result",
            field=models.CharField(
                choices=[
                    ("FAIL", "Fail"),
                    ("PASS", "Pass"),
                    ("REOPENED", "Reopened"),
                ],
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="reconcilevalidationrun",
            name="source",
            field=models.CharField(
                choices=[
                    ("FILE_IMPORT", "File import"),
                    ("SUBMIT_FOR_REVIEW", "Submit for review"),
                    ("VALIDATION_ISSUE_ACKNOWLEDGEMENT", "Validation issue acknowledgement"),
                    ("VALIDATION_ISSUE_REOPEN", "Validation issue reopen"),
                ],
                max_length=32,
            ),
        ),
    ]
