import api from "../../utils/api";

export interface DirectoryEntry {
  name: string;
  path: string;
}

export interface DirectoryListing {
  path: string;
  parent_path: string | null;
  roots: DirectoryEntry[];
  breadcrumbs: DirectoryEntry[];
  entries: DirectoryEntry[];
  total: number;
  offset: number;
  limit: number;
}

export async function listDirectories(params: {
  path?: string;
  search?: string;
  show_hidden?: boolean;
  offset?: number;
}, signal?: AbortSignal) {
  return (await api.get<DirectoryListing>("/admin/filesystem/directories", {
    params,
    signal,
  })).data;
}
