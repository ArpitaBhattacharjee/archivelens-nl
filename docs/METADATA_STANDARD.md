# Metadata Standard

ArchiveLens describes every item with **Dublin Core**, a simple, widely used standard for libraries and
archives. Using a standard means records can later be shared with other systems.

## Fields

| Field | Meaning | Example | Filled by |
|---|---|---|---|
| title | Short descriptive name | Letter about the 1892 cod season | AI, reviewed by archivist |
| creator | Author, photographer or organization | Evening Telegram | AI if stated |
| date | When it was made: `YYYY`, `YYYY-MM` or `YYYY-MM-DD` | 1892-07 | AI only if stated in the item |
| subject | 3–6 topic tags, separated by `;` | fishery; Labrador; schooners | AI |
| description | 1–2 sentences | A merchant describes a poor fishing season. | AI |
| type | Text, StillImage, Sound or MovingImage | Text | Automatic (from file type) |
| format | File format (MIME type) | application/pdf | Automatic |
| coverage | Places mentioned, separated by `;` | Bonavista; Labrador | AI |
| people | People named (local extension) | John Smith | AI |
| language | Language code | en | AI |
| source | Collection the item came from | Smith family papers | Archivist |
| rights | Copyright or use terms | Public domain | Archivist |

**Rules:** AI never invents dates or names. If something isn't in the item, the field stays empty.
Archivist corrections are never overwritten when an item is re-processed.

## File naming (before upload)

`collection_YYYY-MM-DD_short-title.ext`, for example `smith-papers_1892-07_bonavista-letter.pdf`.
Use lowercase, hyphens instead of spaces, and no special characters. Use `0000` if the date is unknown.

## Clean-up and digitization checklist

1. Scan at 300 DPI or higher (grayscale for text, colour for photos).
2. Save multi-page documents as one PDF.
3. Crop borders and straighten pages; this improves OCR accuracy.
4. Remove exact duplicates (the system also blocks identical files automatically).
5. Record the source and rights for every batch.
6. After upload, check items marked **failed** and review the AI metadata.
