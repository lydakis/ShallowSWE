The invoice import CLI is counting duplicate invoice IDs more than once.

Please add a focused regression test for duplicate invoice IDs, then fix the importer so duplicate rows are ignored after the first occurrence. The existing CLI output and public function names should keep working.
