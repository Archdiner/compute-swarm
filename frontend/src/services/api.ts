import axios, { AxiosInstance } from 'axios';

// In production on Vercel, use same domain. In dev, use configured URL or localhost
// If VITE_BACKEND_URL is set, use it. Otherwise:
// - Production: use same domain (empty string = relative URLs work as /api)
// - Development: use localhost:8000
const getBackendUrl = () => {
  const envUrl = import.meta.env.VITE_BACKEND_URL;
  if (envUrl) {
    return envUrl;
  }
  // In production (Vercel), API is on same domain at /api
  // In development, use localhost
  return import.meta.env.PROD ? '' : 'http://localhost:8000';
};

const BACKEND_URL = getBackendUrl();

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: BACKEND_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // Marketplace Stats
  async getStats() {
    const response = await this.client.get('/api/v1/stats');
    return response.data;
  }

  // Jobs
  async submitJob(params: {
    buyer_address: string;
    script: string;
    requirements?: string;
    max_price_per_hour: number;
    timeout_seconds: number;
    required_gpu_type?: string;
    min_vram_gb?: number;
    num_gpus?: number;
  }) {
    const response = await this.client.post('/api/v1/jobs/submit', null, { params });
    return response.data;
  }

  async getJobStatus(jobId: string) {
    const response = await this.client.get(`/api/v1/jobs/${jobId}`);
    return response.data;
  }

  async listBuyerJobs(buyerAddress: string, statusFilter?: string, limit = 50) {
    const params: any = { limit };
    if (statusFilter) params.status_filter = statusFilter;
    const response = await this.client.get(`/api/v1/jobs/buyer/${buyerAddress}`, { params });
    return response.data;
  }

  async listSellerJobs(sellerAddress: string, statusFilter?: string, limit = 50) {
    const params: any = { limit };
    if (statusFilter) params.status_filter = statusFilter;
    const response = await this.client.get(`/api/v1/jobs/seller/${sellerAddress}`, { params });
    return response.data;
  }

  async cancelJob(jobId: string, buyerAddress: string) {
    const response = await this.client.post(`/api/v1/jobs/${jobId}/cancel`, null, {
      params: { buyer_address: buyerAddress },
    });
    return response.data;
  }

  async estimateJobCost(params: {
    timeout_seconds: number;
    required_gpu_type?: string;
    min_vram_gb?: number;
    num_gpus?: number;
  }) {
    const response = await this.client.post('/api/v1/jobs/estimate', null, { params });
    return response.data;
  }

  // Nodes
  async listNodes(gpuType?: string, maxPrice?: number) {
    const params: any = {};
    if (gpuType) params.gpu_type = gpuType;
    if (maxPrice) params.max_price = maxPrice;
    const response = await this.client.get('/api/v1/nodes', { params });
    return response.data;
  }

  async registerNode(data: {
    seller_address: string;
    gpu_info: {
      gpu_type: string;
      device_name: string;
      vram_gb?: number;
      compute_capability?: string;
      num_gpus?: number;
    };
    price_per_hour: number;
  }) {
    const response = await this.client.post('/api/v1/nodes/register', data);
    return response.data;
  }

  async getNode(nodeId: string) {
    const response = await this.client.get(`/api/v1/nodes/${nodeId}`);
    return response.data;
  }

  async nodeHeartbeat(nodeId: string, available: boolean) {
    const response = await this.client.post(`/api/v1/nodes/${nodeId}/heartbeat`, null, {
      params: { available },
    });
    return response.data;
  }

  async markNodeUnavailable(nodeId: string) {
    const response = await this.client.post(`/api/v1/nodes/${nodeId}/unavailable`);
    return response.data;
  }

  // Seller Earnings
  async getSellerEarnings(sellerAddress: string, days = 30) {
    const response = await this.client.get(`/api/v1/sellers/${sellerAddress}/earnings`, {
      params: { days },
    });
    return response.data;
  }

  async getSellerJobHistory(sellerAddress: string, statusFilter?: string, limit = 50, offset = 0) {
    const params: any = { limit, offset };
    if (statusFilter) params.status_filter = statusFilter;
    const response = await this.client.get(`/api/v1/sellers/${sellerAddress}/jobs`, { params });
    return response.data;
  }
}

export const apiClient = new ApiClient();

