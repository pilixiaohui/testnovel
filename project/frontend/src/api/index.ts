import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

type ApiClient = Omit<AxiosInstance, 'get' | 'post' | 'put' | 'delete' | 'patch'> & {
  get<T = unknown, D = unknown>(url: string, config?: AxiosRequestConfig<D>): Promise<T>
  post<T = unknown, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
  put<T = unknown, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
  delete<T = unknown, D = unknown>(url: string, config?: AxiosRequestConfig<D>): Promise<T>
  patch<T = unknown, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
}

export const apiClient = axios.create({
  baseURL,
  timeout: 600000,
}) as ApiClient

apiClient.interceptors.request.use((config) => config)
apiClient.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError<{ detail?: unknown }>) => {
    const detail = error.response?.data?.detail
    if (detail !== undefined && detail !== null) {
      const message = typeof detail === "string" ? detail : JSON.stringify(detail)
      ElMessage.error(message)
    }
    return Promise.reject(error)
  },
)
