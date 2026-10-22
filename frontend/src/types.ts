// Mirrors bibliomap.schema on the backend.

export type SourceFormat =
  | "wos"
  | "scopus"
  | "ris"
  | "pubmed"
  | "bibtex"
  | "openalex"
  | "lens";

export type DocumentType =
  | "article"
  | "review"
  | "conference_paper"
  | "book"
  | "book_chapter"
  | "editorial"
  | "letter"
  | "preprint"
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

export interface ParseResult {
  source_format: SourceFormat;
  records: BibRecord[];
  warnings: ParseWarning[];
}

export interface ImportPreview {
  filename: string | null;
  record_count: number;
  result: ParseResult;
}

export type SearchScope = "title_and_abstract" | "title" | "fulltext";

export const WORK_TYPES = [
  "article",
  "review",
  "conference-paper",
  "book-chapter",
  "book",
  "preprint",
  "letter",
  "editorial",
] as const;

export type WorkType = (typeof WORK_TYPES)[number];

export interface OpenAlexQuery {
  terms: string;
  scope: SearchScope;
  year_from: number | null;
  year_to: number | null;
  types: WorkType[];
  languages: string[];
  open_access_only: boolean;
  max_results: number;
}

export interface OpenAlexCount {
  count: number;
  query_url: string;
}

export interface OpenAlexImport {
  record_count: number;
  total_available: number;
  truncated: boolean;
  cost_usd: number;
  query_url: string;
  result: ParseResult;
}

// --- workspace ----------------------------------------------------------

export interface FilterSpec {
  year_from: number | null;
  year_to: number | null;
  document_types: DocumentType[];
  languages: string[];
  min_cited_by: number | null;
  require_abstract: boolean;
}

export interface Workspace {
  id: string;
  name: string;
  created_at: string;
  version: number;
  filters: FilterSpec;
}

export interface ImportInfo {
  id: number;
  label: string;
  source_format: SourceFormat;
  origin: string | null;
  record_count: number;
  warnings: ParseWarning[];
  created_at: string;
}

export interface WorkspaceSummary {
  workspace: Workspace;
  imports: ImportInfo[];
  counts: {
    identified: number;
    unique: number;
    duplicates_removed: number;
    pending_reviews: number;
    kept: number;
    excluded: number;
  };
}

export interface RecordView {
  id: number;
  import_label: string;
  source_format: SourceFormat;
  title: string;
  authors: string[];
  author_count: number;
  year: number | null;
  source_title: string | null;
  document_type: DocumentType;
  doi: string | null;
  volume: string | null;
  issue: string | null;
  pages: string | null;
  abstract: string | null;
}

export interface PendingPair {
  a: RecordView;
  b: RecordView;
  title_similarity: number;
  reasons: string[];
}

export interface PendingPage {
  total: number;
  items: PendingPair[];
}

export type ExclusionReason = "year" | "document_type" | "language" | "citations" | "no_abstract";

export interface SourceRef {
  record_id: number;
  import_id: number;
  source_format: SourceFormat;
  source_id: string | null;
}

export interface RecordRow {
  merged: { id: number; record: BibRecord; sources: SourceRef[] };
  exclusion_reason: ExclusionReason | null;
}

export interface RecordPage {
  total: number;
  items: RecordRow[];
}

export interface PrismaFlow {
  identified: number;
  identified_by_source: { label: string; count: number }[];
  duplicates_removed: number;
  automation_ineligible: number;
  automation_ineligible_by_reason: Partial<Record<ExclusionReason, number>>;
  other_removed: number;
  screened: number;
  screening_excluded: number | null;
  sought_for_retrieval: number | null;
  not_retrieved: number | null;
  assessed_for_eligibility: number | null;
  reports_excluded: number | null;
  included: number | null;
  pending_duplicate_reviews: number;
}

// --- analysis -----------------------------------------------------------

export interface YearCount {
  year: number;
  count: number;
  mean_citations: number | null;
}

export interface Overview {
  documents: number;
  sources: number;
  authors: number;
  single_authored: number;
  keywords_author: number;
  keywords_index: number;
  references: number;
  year_min: number | null;
  year_max: number | null;
  mean_citations: number;
  total_citations: number;
  mean_authors_per_document: number;
  collaboration_index: number | null;
  international_coauthorship_pct: number | null;
  annual_growth_rate_pct: number | null;
  documents_per_year: YearCount[];
  document_types: Record<string, number>;
}

export interface RankedEntity {
  key: string;
  label: string;
  documents: number;
  citations: number;
  h_index: number;
  g_index: number;
  m_index: number | null;
  first_year: number | null;
}

export interface LotkaFit {
  rows: { documents_written: number; authors: number; proportion: number; fitted_proportion: number }[];
  exponent: number;
  constant: number;
  r_squared: number;
  ks_statistic: number;
}

export interface BradfordAnalysis {
  rows: { rank: number; key: string; label: string; documents: number; cumulative: number; zone: number }[];
  zone_sources: number[];
  zone_documents: number[];
  multiplier: number | null;
}

export interface Statistics {
  overview: Overview;
  top_sources: RankedEntity[];
  top_authors: RankedEntity[];
  top_affiliations: RankedEntity[];
  top_countries: RankedEntity[];
  top_keywords: RankedEntity[];
  lotka: LotkaFit;
  bradford: BradfordAnalysis;
}

export type NetworkType =
  | "co_authorship"
  | "co_occurrence"
  | "citation"
  | "bibliographic_coupling"
  | "co_citation";

export type EntityKind =
  | "author"
  | "source"
  | "keyword"
  | "index_keyword"
  | "affiliation"
  | "country"
  | "reference"
  | "document";

export type Normalization = "none" | "association" | "inclusion";

export interface NetworkOptions {
  type: NetworkType;
  unit: EntityKind;
  min_occurrences: number;
  min_shared: number;
  normalization: Normalization;
  resolution: number;
  min_cluster_size: number;
  max_nodes: number;
  max_edges: number;
}

export interface MapNode {
  id: string;
  label: string;
  x: number;
  y: number;
  cluster: number;
  weight: number;
  link_strength: number;
  documents: number;
  citations: number;
  year: number | null;
}

export interface ScienceMap {
  type: NetworkType;
  unit: EntityKind;
  normalization: Normalization;
  nodes: MapNode[];
  edges: { source: string; target: string; weight: number; raw_weight: number }[];
  clusters: number;
  modularity: number;
  iterations: number;
  truncated_from: number | null;
  edges_before_limit: number | null;
}
