import React, { useState, useEffect } from 'react';
import { Calendar, Clock, Users, TrendingUp, Settings, Play, AlertCircle, Check, X, Edit2, Trash2, UserPlus, Save } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const API_TOKEN = process.env.REACT_APP_API_TOKEN || 'your-secret-key';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [config, setConfig] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [showAddEmployee, setShowAddEmployee] = useState(false);
  const [newEmployeeId, setNewEmployeeId] = useState('');
  const [editingEmployee, setEditingEmployee] = useState(null);

  // Fetch data
  const fetchData = async () => {
    try {
      const headers = {
        'Authorization': `Bearer ${API_TOKEN}`,
        'Content-Type': 'application/json'
      };

      const [statsRes, employeesRes, configRes, logsRes] = await Promise.all([
        fetch(`${API_URL}/api/stats`, { headers }),
        fetch(`${API_URL}/api/employees`, { headers }),
        fetch(`${API_URL}/api/config`, { headers }),
        fetch(`${API_URL}/api/logs?limit=50`, { headers })
      ]);

      setStats(await statsRes.json());
      setEmployees(await employeesRes.json());
      setConfig(await configRes.json());
      setLogs(await logsRes.json());
      setLoading(false);
    } catch (error) {
      console.error('Error fetching data:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  // Add employee
  const addEmployee = async () => {
    try {
      const response = await fetch(`${API_URL}/api/employees?employee_id=${newEmployeeId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${API_TOKEN}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        setShowAddEmployee(false);
        setNewEmployeeId('');
        fetchData();
      } else {
        alert('Nie można dodać pracownika. Sprawdź ID.');
      }
    } catch (error) {
      console.error('Error adding employee:', error);
    }
  };

  // Update employee
  const updateEmployee = async (id, updates) => {
    try {
      const response = await fetch(`${API_URL}/api/employees/${id}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${API_TOKEN}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(updates)
      });

      if (response.ok) {
        setEditingEmployee(null);
        fetchData();
      }
    } catch (error) {
      console.error('Error updating employee:', error);
    }
  };

  // Delete employee
  const deleteEmployee = async (id) => {
    if (!window.confirm('Czy na pewno chcesz usunąć tego pracownika?')) return;

    try {
      const response = await fetch(`${API_URL}/api/employees/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${API_TOKEN}`
        }
      });

      if (response.ok) {
        fetchData();
      }
    } catch (error) {
      console.error('Error deleting employee:', error);
    }
  };

  // Update config
  const updateConfig = async (newConfig) => {
    try {
      const response = await fetch(`${API_URL}/api/config`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${API_TOKEN}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newConfig)
      });

      if (response.ok) {
        fetchData();
        alert('Konfiguracja zaktualizowana!');
      }
    } catch (error) {
      console.error('Error updating config:', error);
    }
  };

  // Manual trigger
  const triggerUpdate = async () => {
    if (!window.confirm('Czy na pewno chcesz ręcznie uruchomić aktualizację?')) return;

    try {
      const response = await fetch(`${API_URL}/api/trigger-update`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${API_TOKEN}`
        }
      });

      if (response.ok) {
        alert('Aktualizacja została uruchomiona!');
      }
    } catch (error) {
      console.error('Error triggering update:', error);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Ładowanie...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <h1 className="text-3xl font-bold text-gray-900">
              Everhour Time Multiplier
            </h1>
            <button
              onClick={triggerUpdate}
              className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 flex items-center gap-2"
            >
              <Play className="w-4 h-4" />
              Uruchom ręcznie
            </button>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-gray-800 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            {['overview', 'employees', 'logs', 'settings'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-4 px-3 text-sm font-medium ${
                  activeTab === tab
                    ? 'border-b-2 border-white'
                    : 'hover:border-b-2 hover:border-gray-400'
                }`}
              >
                {tab === 'overview' && 'Przegląd'}
                {tab === 'employees' && 'Pracownicy'}
                {tab === 'logs' && 'Historia'}
                {tab === 'settings' && 'Ustawienia'}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Overview Tab */}
        {activeTab === 'overview' && stats && (
          <div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              <div className="bg-white p-6 rounded-lg shadow">
                <div className="flex items-center justify-between mb-4">
                  <Users className="w-8 h-8 text-blue-600" />
                  <span className="text-2xl font-bold">{stats.active_employees}/{stats.total_employees}</span>
                </div>
                <p className="text-gray-600">Aktywni pracownicy</p>
              </div>

              <div className="bg-white p-6 rounded-lg shadow">
                <div className="flex items-center justify-between mb-4">
                  <Clock className="w-8 h-8 text-green-600" />
                  <span className="text-2xl font-bold">
                    {stats.next_run ? new Date(stats.next_run).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' }) : '--:--'}
                  </span>
                </div>
                <p className="text-gray-600">Następne uruchomienie</p>
              </div>

              <div className="bg-white p-6 rounded-lg shadow">
                <div className="flex items-center justify-between mb-4">
                  <TrendingUp className="w-8 h-8 text-purple-600" />
                  <span className="text-2xl font-bold">+{stats.total_hours_added_this_week.toFixed(1)}h</span>
                </div>
                <p className="text-gray-600">Dodane ten tydzień</p>
              </div>

              <div className="bg-white p-6 rounded-lg shadow">
                <div className="flex items-center justify-between mb-4">
                  <Calendar className="w-8 h-8 text-orange-600" />
                  <span className="text-2xl font-bold">+{stats.total_hours_added_this_month.toFixed(1)}h</span>
                </div>
                <p className="text-gray-600">Dodane ten miesiąc</p>
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow">
              <h2 className="text-xl font-bold mb-4">Status systemu</h2>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Status:</span>
                  <span className="flex items-center gap-2">
                    <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                    <span className="text-green-600 font-medium">Aktywny</span>
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Tryb:</span>
                  <span className={`font-medium ${config?.dry_run ? 'text-yellow-600' : 'text-green-600'}`}>
                    {config?.dry_run ? 'Testowy (DRY RUN)' : 'Produkcyjny'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Ostatnie uruchomienie:</span>
                  <span className="font-medium">
                    {stats.last_run 
                      ? new Date(stats.last_run).toLocaleString('pl-PL')
                      : 'Brak danych'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Employees Tab */}
        {activeTab === 'employees' && (
          <div>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold">Pracownicy</h2>
              <button
                onClick={() => setShowAddEmployee(true)}
                className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 flex items-center gap-2"
              >
                <UserPlus className="w-4 h-4" />
                Dodaj pracownika
              </button>
            </div>

            {showAddEmployee && (
              <div className="bg-white p-4 rounded-lg shadow mb-6">
                <h3 className="font-bold mb-3">Dodaj nowego pracownika</h3>
                <div className="flex gap-3">
                  <input
                    type="text"
                    placeholder="ID pracownika z Everhour"
                    value={newEmployeeId}
                    onChange={(e) => setNewEmployeeId(e.target.value)}
                    className="flex-1 px-3 py-2 border rounded-md"
                  />
                  <button
                    onClick={addEmployee}
                    className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
                  >
                    Dodaj
                  </button>
                  <button
                    onClick={() => {
                      setShowAddEmployee(false);
                      setNewEmployeeId('');
                    }}
                    className="bg-gray-400 text-white px-4 py-2 rounded-md hover:bg-gray-500"
                  >
                    Anuluj
                  </button>
                </div>
              </div>
            )}

            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Imię i nazwisko
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Email
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Mnożnik
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Akcje
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {employees.map((employee) => (
                    <tr key={employee.id}>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{employee.name}</div>
                        <div className="text-sm text-gray-500">ID: {employee.id}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {employee.email || '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {editingEmployee === employee.id ? (
                          <input
                            type="number"
                            step="0.1"
                            defaultValue={employee.multiplier}
                            className="w-20 px-2 py-1 border rounded"
                            id={`multiplier-${employee.id}`}
                          />
                        ) : (
                          <span className="text-sm font-medium">{employee.multiplier}x</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          employee.active 
                            ? 'bg-green-100 text-green-800' 
                            : 'bg-red-100 text-red-800'
                        }`}>
                          {employee.active ? 'Aktywny' : 'Nieaktywny'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        {editingEmployee === employee.id ? (
                          <div className="flex gap-2">
                            <button
                              onClick={() => {
                                const multiplier = parseFloat(document.getElementById(`multiplier-${employee.id}`).value);
                                updateEmployee(employee.id, { multiplier });
                              }}
                              className="text-green-600 hover:text-green-900"
                            >
                              <Save className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => setEditingEmployee(null)}
                              className="text-gray-600 hover:text-gray-900"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex gap-2">
                            <button
                              onClick={() => setEditingEmployee(employee.id)}
                              className="text-blue-600 hover:text-blue-900"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => updateEmployee(employee.id, { active: !employee.active })}
                              className="text-yellow-600 hover:text-yellow-900"
                            >
                              {employee.active ? <X className="w-4 h-4" /> : <Check className="w-4 h-4" />}
                            </button>
                            <button
                              onClick={() => deleteEmployee(employee.id)}
                              className="text-red-600 hover:text-red-900"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Logs Tab */}
        {activeTab === 'logs' && (
          <div>
            <h2 className="text-2xl font-bold mb-6">Historia operacji</h2>
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Data
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Pracownik
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Oryginalne godziny
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Zaktualizowane godziny
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Różnica
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {logs.map((log) => (
                    <tr key={log.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {new Date(log.created_at).toLocaleString('pl-PL')}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {log.employee_name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {log.original_hours.toFixed(2)}h
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {log.updated_hours.toFixed(2)}h
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-green-600">
                        +{(log.updated_hours - log.original_hours).toFixed(2)}h
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          log.status === 'success' 
                            ? 'bg-green-100 text-green-800' 
                            : 'bg-red-100 text-red-800'
                        }`}>
                          {log.status === 'success' ? 'Sukces' : 'Błąd'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Settings Tab */}
        {activeTab === 'settings' && config && (
          <div>
            <h2 className="text-2xl font-bold mb-6">Ustawienia</h2>
            <div className="bg-white rounded-lg shadow p-6 max-w-2xl">
              <form onSubmit={(e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                updateConfig({
                  run_hour: parseInt(formData.get('run_hour')),
                  run_minute: parseInt(formData.get('run_minute')),
                  default_multiplier: parseFloat(formData.get('default_multiplier')),
                  dry_run: formData.get('dry_run') === 'true'
                });
              }}>
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Godzina uruchomienia
                    </label>
                    <div className="flex gap-2 items-center">
                      <input
                        type="number"
                        name="run_hour"
                        min="0"
                        max="23"
                        defaultValue={config.run_hour}
                        className="w-20 px-3 py-2 border rounded-md"
                      />
                      <span className="text-gray-500">:</span>
                      <input
                        type="number"
                        name="run_minute"
                        min="0"
                        max="59"
                        defaultValue={config.run_minute}
                        className="w-20 px-3 py-2 border rounded-md"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Domyślny mnożnik
                    </label>
                    <input
                      type="number"
                      name="default_multiplier"
                      step="0.1"
                      defaultValue={config.default_multiplier}
                      className="w-32 px-3 py-2 border rounded-md"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Tryb działania
                    </label>
                    <select
                      name="dry_run"
                      defaultValue={config.dry_run.toString()}
                      className="px-3 py-2 border rounded-md"
                    >
                      <option value="true">Testowy (DRY RUN)</option>
                      <option value="false">Produkcyjny</option>
                    </select>
                  </div>

                  <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
                    <div className="flex">
                      <AlertCircle className="w-5 h-5 text-yellow-400 mr-3" />
                      <div className="text-sm text-yellow-800">
                        <p className="font-medium">Uwaga!</p>
                        <p className="mt-1">
                          Zmiana trybu na "Produkcyjny" spowoduje rzeczywiste zmiany w Everhour.
                          Upewnij się, że chcesz to zrobić.
                        </p>
                      </div>
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700"
                  >
                    Zapisz ustawienia
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
