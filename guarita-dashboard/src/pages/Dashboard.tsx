import { useEffect, useState, useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import { api } from '../services/api';
import { Search, ChevronDown, LogOut, X } from 'lucide-react';

// --- TIPAGEM ---
interface Department {
  id: number;
  name: string;
}

interface Room {
  id: number;
  name: string;
  department: Department;
}

interface IOT {
  id: number;
  name: string;
  status: boolean;
  room: Room;
}

interface UserPermission {
  id: number;
  user: {
    username: string;
    role: string;
  };
}

export function Dashboard() {
  const { logout } = useContext(AuthContext);
  
  // Dados Principais
  const [iots, setIots] = useState<IOT[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  
  // Filtros e UI
  const [menuOpen, setMenuOpen] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDept, setSelectedDept] = useState<number | null>(null);
  const [selectedDeptName, setSelectedDeptName] = useState('Todas as áreas');

  // Modal e Detalhes
  const [selectedIoT, setSelectedIoT] = useState<IOT | null>(null);
  const [responsibles, setResponsibles] = useState<string[]>([]);
  const [loadingResp, setLoadingResp] = useState(false);

  // Inicialização e Polling (Atualiza a cada 5s)
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); 
    return () => clearInterval(interval);
  }, []);

  // Ao selecionar um IoT, busca os responsáveis
  useEffect(() => {
    if (selectedIoT) {
      fetchResponsibles(selectedIoT.room.id);
    } else {
      setResponsibles([]);
    }
  }, [selectedIoT]);

  async function fetchData() {
    try {
      const deptRes = await api.get('/departments/');
      const deptData = deptRes.data.data?.result || deptRes.data.data || [];
      setDepartments(Array.isArray(deptData) ? deptData : []);

      const iotsRes = await api.get('/iots/');
      const payload = iotsRes.data; 
      
      // Lógica robusta para encontrar o array de resultados
      if (payload.data && Array.isArray(payload.data.result)) {
          setIots(payload.data.result); 
      } else if (Array.isArray(payload.data)) {
          setIots(payload.data);
      } else {
          setIots([]);
      }
    } catch (error) {
      console.error("Erro ao buscar dados", error);
    }
  }

  async function fetchResponsibles(roomId: number) {
    setLoadingResp(true);
    try {
      const res = await api.get(`/user-permissions/?room=${roomId}`);
      // Adaptação caso venha paginado ou lista direta
      const data = res.data.results || res.data; 
      
      if (Array.isArray(data)) {
        const names = data.map((p: UserPermission) => p.user?.username || 'Desconhecido');
        setResponsibles(names);
      }
    } catch (error) {
      console.error("Erro ao buscar responsáveis", error);
      setResponsibles(['Erro ao carregar lista']);
    } finally {
      setLoadingResp(false);
    }
  }

  // Lógica de Filtragem (Busca + Departamento)
  const filteredIots = iots.filter(iot => {
    const searchString = searchTerm.toLowerCase();
    const iotName = iot.name ? iot.name.toLowerCase() : '';
    const roomName = iot.room?.name ? iot.room.name.toLowerCase() : '';
    
    const matchesSearch = roomName.includes(searchString) || iotName.includes(searchString);
    const matchesDept = selectedDept ? iot.room?.department?.id === selectedDept : true;
    
    return matchesSearch && matchesDept;
  });

  return (
    <div className="min-h-screen bg-gray-100 font-sans">
      
      {/* --- HEADER --- */}
      <header className="bg-brand-green px-8 py-4 flex items-center justify-between shadow-md relative z-20">
        
        {/* LOGO IFACCESS (Atualizado) */}
        <div className="flex items-center gap-3 select-none">
          <div className="relative w-10 h-10 bg-white rounded-lg flex items-center justify-center shadow-sm">
             {/* Arco Verde */}
             <div className="w-4 h-5 border-l-4 border-t-4 border-[#1B5E20] rounded-tl-md mt-1 mr-0.5"></div>
             {/* Ponto Vermelho */}
             <div className="absolute top-2 right-2 w-2.5 h-2.5 bg-[#D32F2F] rounded-full"></div>
          </div>
          <h1 className="font-bold text-2xl tracking-tight text-white">IFAccess</h1>
        </div>

        {/* BUSCA E FILTRO */}
        <div className="flex gap-4 w-full max-w-3xl mx-8">
            <div className="relative flex-1">
                <input 
                    type="text" 
                    placeholder="Buscar porta" 
                    className="w-full pl-4 pr-10 py-2.5 rounded-md focus:outline-none shadow-sm text-gray-700"
                    value={searchTerm}
                    onChange={e => setSearchTerm(e.target.value)}
                />
                <Search className="absolute right-3 top-3 text-gray-400" size={18} />
            </div>
            
            <div className="relative">
                <button 
                    onClick={() => setFilterOpen(!filterOpen)}
                    className="bg-gray-100 hover:bg-white text-gray-600 px-4 py-2.5 rounded-md flex items-center justify-between min-w-[200px] shadow-sm transition-colors"
                >
                    <span className="truncate max-w-[150px]">{selectedDeptName}</span>
                    <ChevronDown size={16} />
                </button>

                {filterOpen && (
                    <div className="absolute top-full mt-2 w-64 bg-white rounded-md shadow-xl py-2 z-30 max-h-80 overflow-y-auto border border-gray-100">
                        <button 
                            onClick={() => { setSelectedDept(null); setSelectedDeptName('Todas as áreas'); setFilterOpen(false); }}
                            className="w-full text-left px-4 py-2 hover:bg-gray-50 text-sm text-gray-700 font-medium"
                        >
                            Todas as áreas
                        </button>
                        {departments.map(dept => (
                            <button 
                                key={dept.id}
                                onClick={() => { setSelectedDept(dept.id); setSelectedDeptName(dept.name); setFilterOpen(false); }}
                                className="w-full text-left px-4 py-2 hover:bg-gray-50 text-sm text-gray-600"
                            >
                                {dept.name}
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </div>

        {/* MENU OPÇÕES / SAIR */}
        <div className="relative">
            <button 
                onClick={() => setMenuOpen(!menuOpen)}
                className="border border-white/50 text-white px-6 py-2 rounded-lg font-semibold hover:bg-white/10 transition text-sm"
            >
                Opções
            </button>
            {menuOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 z-30 border border-gray-100">
                    <button 
                        onClick={logout}
                        className="w-full text-left px-4 py-2 text-gray-700 hover:bg-gray-50 flex items-center gap-2 text-sm"
                    >
                        <LogOut size={14} /> Sair
                    </button>
                </div>
            )}
        </div>
      </header>

      {/* --- CONTEÚDO PRINCIPAL (GRID) --- */}
      <main className="p-8 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {filteredIots.length === 0 && (
                <div className="col-span-full text-center text-gray-500 mt-10">
                    Nenhuma porta encontrada.
                </div>
            )}

            {filteredIots.map((iot) => (
                <div 
                    key={iot.id} 
                    onClick={() => setSelectedIoT(iot)}
                    className="bg-white rounded-xl shadow-sm p-5 cursor-pointer hover:shadow-lg transition-all duration-300 flex flex-col justify-between h-36 border border-gray-100 group"
                >
                    <h3 className="text-base font-bold text-gray-800 uppercase leading-snug group-hover:text-brand-green transition-colors">
                        {iot.room?.name || 'Sala Desconhecida'}
                    </h3>
                    
                    <div className="self-end mt-auto">
                        <span className={`px-3 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wide ${
                            !iot.status 
                            ? 'border-status-green text-status-green' 
                            : 'border-status-red text-status-red'
                        }`}>
                            {!iot.status ? 'FECHADO' : 'ABERTO'}
                        </span>
                    </div>
                </div>
            ))}
        </div>
      </main>

      {/* --- MODAL DE DETALHES --- */}
      {selectedIoT && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4 backdrop-blur-[2px]">
            <div className="bg-white rounded-sm shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col relative animate-fade-in">
                
                {/* Header do Modal (Verde) */}
                <div className="bg-brand-green p-6 flex items-center justify-between shadow-md">
                    
                    {/* LOGO IFACCESS NO MODAL (Atualizado) */}
                    <div className="flex items-center gap-3 select-none">
                        <div className="relative w-9 h-9 bg-white rounded-lg flex items-center justify-center shadow-sm">
                            <div className="w-3.5 h-4 border-l-[3px] border-t-[3px] border-[#1B5E20] rounded-tl-md mt-1 mr-0.5"></div>
                            <div className="absolute top-2 right-2 w-2 h-2 bg-[#D32F2F] rounded-full"></div>
                        </div>
                        <h1 className="font-bold text-xl tracking-tight text-white">IFAccess</h1>
                    </div>
                    
                    <button onClick={() => setSelectedIoT(null)} className="text-white hover:text-gray-200 transition">
                        <X size={28} />
                    </button>
                </div>

                {/* Corpo do Modal */}
                <div className="p-8">
                    <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-6 border-b pb-2">
                        INFORMAÇÕES
                    </h2>

                    <div className="space-y-6">
                        <div>
                            <p className="text-xs font-bold text-gray-400 uppercase mb-1">Título:</p>
                            <p className="text-lg font-bold text-gray-800 uppercase">
                                {selectedIoT.room?.name}
                            </p>
                        </div>

                        <div>
                            <p className="text-xs font-bold text-gray-400 uppercase mb-1">Status:</p>
                            <p className={`text-lg font-bold uppercase ${!selectedIoT.status ? 'text-status-green' : 'text-status-red'}`}>
                                {!selectedIoT.status ? 'FECHADO' : 'ABERTO'}
                            </p>
                        </div>

                        <div>
                            <p className="text-xs font-bold text-gray-400 uppercase mb-1">Localização:</p>
                            <p className="text-lg font-bold text-purple-900 uppercase">
                                {selectedIoT.room?.department?.name}
                            </p>
                        </div>

                        <div>
                            <p className="text-xs font-bold text-gray-400 uppercase mb-1">Responsáveis:</p>
                            <p className="text-lg font-bold text-purple-900 uppercase leading-relaxed">
                                {loadingResp ? (
                                    <span className="text-gray-400 text-sm font-normal italic">Carregando...</span>
                                ) : responsibles.length > 0 ? (
                                    responsibles.join(', ')
                                ) : (
                                    <span className="text-gray-400 text-sm font-normal">Nenhum responsável direto vinculado.</span>
                                )}
                            </p>
                        </div>
                    </div>
                    
                    <div className="mt-8 flex justify-end">
                        <button 
                            onClick={() => setSelectedIoT(null)}
                            className="bg-gray-100 text-gray-600 px-6 py-2 rounded hover:bg-gray-200 transition font-bold text-sm"
                        >
                            Fechar
                        </button>
                    </div>
                </div>
                
                <div className="bg-gray-50 p-4 text-center text-xs text-gray-400 border-t">
                    2025. Desenvolvido por EJ Turing Consultoria e Desenvolvimento.
                </div>
            </div>
        </div>
      )}
    </div>
  );
}