// Browser ES module. Works with React, Vue, or plain JavaScript.
export class ApiError extends Error {
  constructor(status, error) {
    super(error?.message || `Request failed (${status})`);
    this.name = 'ApiError';
    this.status = status;
    this.details = error?.details || [];
  }
}

export function createApiClient(baseUrl = 'http://localhost:8000/api', apiKey = '') {
  async function request(path, { method = 'GET', body, query, signal } = {}) {
    const url = new URL(baseUrl.replace(/\/$/, '') + path);
    for (const [key, value] of Object.entries(query || {})) {
      if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
    }
    const response = await fetch(url, {
      method,
      signal,
      headers: {
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(apiKey ? { 'X-API-Key': apiKey } : {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    const data = await response.json();
    if (!response.ok) throw new ApiError(response.status, data.error);
    return data;
  }
  return {
    request,
    students: (query) => request('/students', { query }),
    student: (id) => request(`/students/${id}`),
    createStudent: (body) => request('/students', { method: 'POST', body }),
    updateStudent: (id, body) => request(`/students/${id}`, { method: 'PATCH', body }),
    setStudentSkills: (id, skill_ids) => request(`/students/${id}/skills`, { method: 'PUT', body: { skill_ids } }),
    projects: (query) => request('/projects', { query }),
    createProject: (body) => request('/projects', { method: 'POST', body }),
    teams: (query) => request('/teams', { query }),
    team: (id) => request(`/teams/${id}`),
    createTeam: (body) => request('/teams', { method: 'POST', body }),
    setTeamSkills: (id, skill_ids) => request(`/teams/${id}/skills`, { method: 'PUT', body: { skill_ids } }),
    skills: (query) => request('/skills', { query }),
    matches: (id, query) => request(`/students/${id}/matches`, { query }),
    joinRequests: (query) => request('/requests', { query }),
    requestToJoin: (student_id, team_id) => request('/requests', { method: 'POST', body: { student_id, team_id } }),
    decideRequest: (id, request_status) => request(`/requests/${id}`, { method: 'PATCH', body: { request_status } }),
    withdrawRequest: (id) => request(`/requests/${id}`, { method: 'DELETE' }),
    leaveTeam: (teamId, studentId) => request(`/teams/${teamId}/members/${studentId}`, { method: 'DELETE' }),
    dashboard: () => request('/dashboard'),
  };
}
