export interface ResponseBase<T = unknown> {
  code: number
  message: string
  data: T
}

export interface PaginatedResponse<T = unknown> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface ImportErrorItem {
  row_number: number
  field: string | null
  message: string
}

export interface ImportValidateResponse {
  import_id: string
  checksum: string
  total_rows: number
  valid_rows: number
  error_rows: number
  errors: ImportErrorItem[]
}

export interface ImportCommitRequest {
  import_id: string
  checksum: string
  allow_overwrite?: boolean
}

export interface ImportCommitResponse {
  import_id: string
  checksum: string
  status: string
  imported_rows: number
  created_at: string
}

export interface ImportPreviewRow {
  row_number: number
  data: Record<string, unknown>
}

export interface ImportPreviewResponse {
  import_id: string
  checksum: string
  page: number
  page_size: number
  total_rows: number
  rows: ImportPreviewRow[]
}
