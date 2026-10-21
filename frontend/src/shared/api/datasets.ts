import { useQuery } from "@tanstack/vue-query";
import api from "../../utils/api";
export interface Dataset {
  id: number;
  name: string;
  description: string | null;
  image_path: string;
  label_path: string | null;
  total_images: number;
  labeled_images: number;
  is_active: boolean;
}
export interface DatasetImage {
  id: number;
  dataset_id: number;
  filename: string;
  width: number;
  height: number;
  status: string;
  candidates?: unknown[];
}
export interface Page<T> {
  items: T[];
  total: number;
}
export const datasetKeys = {
  all: ["datasets"] as const,
  detail: (id: number) => ["datasets", id] as const,
  images: (id: number) => ["datasets", id, "images"] as const,
};
export const datasetApi = {
  list: async (signal?: AbortSignal) =>
    (await api.get<Dataset[]>("/datasets", { signal })).data,
  detail: async (id: number, signal?: AbortSignal) =>
    (await api.get<Dataset>(`/datasets/${id}`, { signal })).data,
  images: async (
    id: number,
    page: number,
    pageSize: number,
    signal?: AbortSignal,
  ) =>
    (
      await api.get<Page<DatasetImage>>(`/datasets/${id}/images`, {
        params: { page, page_size: pageSize },
        signal,
      })
    ).data,
};
export function useDatasets() {
  return useQuery({
    queryKey: datasetKeys.all,
    queryFn: ({ signal }) => datasetApi.list(signal),
  });
}
