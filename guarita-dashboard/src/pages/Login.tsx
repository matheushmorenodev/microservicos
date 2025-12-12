import { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import { api } from '../services/api';
import { User, Lock, ArrowRight, AlertCircle } from 'lucide-react';

export function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  
  const { login } = useContext(AuthContext);
  const navigate = useNavigate();

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Limpeza de espaços (Trim)
    const userClean = username.trim();
    const passClean = password.trim();

    try {
      const response = await api.post('/auth/login/', {
        username: userClean,
        password: passClean
      });
      
      login(response.data.access);
      navigate('/dashboard');

    } catch (err: any) {
      console.error(err);
      if (err.response && err.response.status === 401) {
        setError('Usuário ou senha incorretos.');
      } else {
        setError('Erro ao conectar com o servidor.');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-brand-green flex flex-col items-center justify-center p-4 font-sans">
      
      {/* --- LOGO IFACCESS (Versão Grande) --- */}
      <div className="flex flex-col items-center mb-8 gap-4 animate-fade-in-down">
        {/* Ícone CSS Puro */}
        <div className="relative w-20 h-20 bg-white rounded-2xl flex items-center justify-center shadow-xl">
            {/* Arco Verde */}
            <div className="w-8 h-10 border-l-[6px] border-t-[6px] border-[#1B5E20] rounded-tl-xl mt-2 mr-1"></div>
            {/* Ponto Vermelho */}
            <div className="absolute top-4 right-4 w-4 h-4 bg-[#D32F2F] rounded-full"></div>
        </div>
        
        {/* Texto */}
        <h1 className="text-4xl font-bold text-white tracking-tight">IFAccess</h1>
        <p className="text-green-100 text-sm opacity-90">Controle de Acesso Inteligente</p>
      </div>

      {/* --- CARD DE LOGIN --- */}
      <div className="bg-white w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden animate-fade-in-up">
        <div className="p-8">
          <h2 className="text-xl font-bold text-gray-800 text-center mb-6">Bem-vindo</h2>
          
          <form onSubmit={handleLogin} className="space-y-5">
            {/* Input Usuário */}
            <div className="relative group">
              <User className="absolute left-3 top-3 text-gray-400 group-focus-within:text-brand-green transition-colors" size={20} />
              <input 
                type="text" 
                placeholder="Matrícula ou Usuário" 
                className="w-full pl-10 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:border-brand-green focus:ring-1 focus:ring-brand-green transition-all"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
              />
            </div>

            {/* Input Senha */}
            <div className="relative group">
              <Lock className="absolute left-3 top-3 text-gray-400 group-focus-within:text-brand-green transition-colors" size={20} />
              <input 
                type="password" 
                placeholder="Senha" 
                className="w-full pl-10 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:border-brand-green focus:ring-1 focus:ring-brand-green transition-all"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
            </div>

            {/* Mensagem de Erro */}
            {error && (
              <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 p-3 rounded-lg border border-red-100 animate-pulse">
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}

            {/* Botão Entrar */}
            <button 
              type="submit" 
              disabled={loading}
              className="w-full bg-brand-green text-white py-3 rounded-lg font-bold hover:bg-[#144818] transition-all transform active:scale-95 flex items-center justify-center gap-2 shadow-lg hover:shadow-xl disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {loading ? (
                'Entrando...'
              ) : (
                <>
                  Acessar Painel <ArrowRight size={20} />
                </>
              )}
            </button>
          </form>
        </div>
        
        {/* Rodapé do Card */}
        <div className="bg-gray-50 p-4 text-center border-t border-gray-100">
           <p className="text-xs text-gray-400">
             Esqueceu sua senha? Entre em contato com o NTI.
           </p>
        </div>
      </div>

      {/* Rodapé da Página */}
      <div className="mt-8 text-center text-green-100/60 text-xs">
        &copy; 2025 IFAccess. Todos os direitos reservados.
      </div>

    </div>
  );
}