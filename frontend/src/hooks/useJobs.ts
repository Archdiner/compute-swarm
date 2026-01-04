import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../services/api';

export interface Job {
  job_id: string;
  status: string;
  buyer_address: string;
  seller_address?: string;
  script: string;
  max_price_per_hour: number;
  timeout_seconds: number;
  created_at?: string;
  claimed_at?: string;
  started_at?: string;
  completed_at?: string;
  execution_duration_seconds?: number;
  total_cost_usd?: number;
  payment_tx_hash?: string;
  result_output?: string;
  result_error?: string;
  node_id?: string;
}

export function useBuyerJobs(buyerAddress: string | null, autoRefresh = true) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    if (!buyerAddress) {
      setJobs([]);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.listBuyerJobs(buyerAddress);
      setJobs(data.jobs || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch jobs');
      console.error('Error fetching jobs:', err);
    } finally {
      setLoading(false);
    }
  }, [buyerAddress]);

  useEffect(() => {
    fetchJobs();
    
    if (autoRefresh) {
      const interval = setInterval(fetchJobs, 5000); // Poll every 5 seconds
      return () => clearInterval(interval);
    }
  }, [fetchJobs, autoRefresh]);

  const refresh = useCallback(() => {
    fetchJobs();
  }, [fetchJobs]);

  return { jobs, loading, error, refresh };
}

export function useSellerJobs(sellerAddress: string | null, autoRefresh = true) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    if (!sellerAddress) {
      setJobs([]);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.listSellerJobs(sellerAddress);
      setJobs(data.jobs || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch jobs');
      console.error('Error fetching seller jobs:', err);
    } finally {
      setLoading(false);
    }
  }, [sellerAddress]);

  useEffect(() => {
    fetchJobs();
    
    if (autoRefresh) {
      const interval = setInterval(fetchJobs, 5000);
      return () => clearInterval(interval);
    }
  }, [fetchJobs, autoRefresh]);

  const refresh = useCallback(() => {
    fetchJobs();
  }, [fetchJobs]);

  return { jobs, loading, error, refresh };
}

export function useJobStatus(jobId: string | null, autoRefresh = true) {
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchJob = useCallback(async () => {
    if (!jobId) {
      setJob(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getJobStatus(jobId);
      setJob(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch job status');
      console.error('Error fetching job status:', err);
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    fetchJob();
    
    if (autoRefresh && jobId) {
      const interval = setInterval(() => {
        fetchJob();
        // Stop polling if job is in terminal state
        if (job && ['COMPLETED', 'FAILED', 'CANCELLED'].includes(job.status)) {
          clearInterval(interval);
        }
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [fetchJob, autoRefresh, jobId, job]);

  const refresh = useCallback(() => {
    fetchJob();
  }, [fetchJob]);

  return { job, loading, error, refresh };
}

