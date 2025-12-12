// src/services/api.ts
import axios from 'axios';

// URL do Kong Gateway rodando no Docker (Porta 8000)
const API_URL = 'http://localhost:8000/api'; 

export const api = axios.create({
  baseURL: API_URL,
});

// Interceptor para adicionar o Token JWT automaticamente em todas as requisições
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});