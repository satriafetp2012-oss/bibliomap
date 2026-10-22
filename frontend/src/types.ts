// Mirrors bibliomap.schema on the backend.

export type SourceFormat = "wos" | "scopus" | "ris" | "pubmed";

export type DocumentType =
  | "article"
  | "review"
  | "conference_paper"
  | "book"
  | "book_chapter"
  | "editorial"
  | "letter"
  | "other";

export interface Author {
  name: string;
  full_name: string | null;
  orcid: string | null;
  affiliations: string[];
}

export interface BibRecord {
  source_format: SourceFormat;
  source_id: string | null;
  title: string;
  authors: Author[];
  year: number | null;
  source_title: string | null;
  document_type: DocumentType;
  doi: string | null;
  cited_by: number | null;
}

export interface ParseWarning {
  record_index: number | null;
  message: string;
}

export interface ImportPreview {
  filename: string | null;
  record_count: number;
  result: {
    source_format: SourceFormat;
    records: BibRecord[];
    warnings: ParseWarning[];
  };
}
