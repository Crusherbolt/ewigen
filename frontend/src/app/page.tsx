'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

interface Project {
  id: number;
  name: string;
  description: string;
  status: string;
  progress: number;
  total_videos: number;
  created_at: string;
}

export default function HomePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.push('/login');
        return;
      }

      const response = await fetch('http://localhost:8000/api/v1/projects/', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch projects');
      }

      const data = await response.json();
      setProjects(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'processing':
        return 'bg-blue-100 text-blue-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <h1 className="text-3xl font-bold text-gray-900">
              Virtual Environment Platform
            </h1>
            <div className="flex gap-4">
              <Link
                href="/projects/new"
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"
              >
                New Project
              </Link>
              <button
                onClick={() => {
                  localStorage.removeItem('access_token');
                  router.push('/login');
                }}
                className="bg-gray-200 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-300 transition"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="text-sm text-gray-500">Total Projects</div>
            <div className="text-3xl font-bold text-gray-900">{projects.length}</div>
          </div>
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="text-sm text-gray-500">Processing</div>
            <div className="text-3xl font-bold text-blue-600">
              {projects.filter(p => p.status === 'processing').length}
            </div>
          </div>
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="text-sm text-gray-500">Completed</div>
            <div className="text-3xl font-bold text-green-600">
              {projects.filter(p => p.status === 'completed').length}
            </div>
          </div>
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="text-sm text-gray-500">Total Videos</div>
            <div className="text-3xl font-bold text-gray-900">
              {projects.reduce((sum, p) => sum + p.total_videos, 0)}
            </div>
          </div>
        </div>

        {/* Projects List */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">Your Projects</h2>
          </div>
          
          {projects.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <svg
                className="mx-auto h-12 w-12 text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"
                />
              </svg>
              <h3 className="mt-2 text-sm font-medium text-gray-900">No projects</h3>
              <p className="mt-1 text-sm text-gray-500">
                Get started by creating a new project.
              </p>
              <div className="mt-6">
                <Link
                  href="/projects/new"
                  className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
                >
                  Create Project
                </Link>
              </div>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {projects.map((project) => (
                <Link
                  key={project.id}
                  href={`/projects/${project.id}`}
                  className="block hover:bg-gray-50 transition"
                >
                  <div className="px-6 py-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <h3 className="text-lg font-medium text-gray-900">
                          {project.name}
                        </h3>
                        <p className="text-sm text-gray-500 mt-1">
                          {project.description || 'No description'}
                        </p>
                        <div className="flex items-center gap-4 mt-2">
                          <span className={`px-2 py-1 text-xs font-medium rounded ${getStatusColor(project.status)}`}>
                            {project.status}
                          </span>
                          <span className="text-sm text-gray-500">
                            {project.total_videos} videos
                          </span>
                          <span className="text-sm text-gray-500">
                            Created {new Date(project.created_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                      
                      {project.status === 'processing' && (
                        <div className="ml-4">
                          <div className="w-32">
                            <div className="flex justify-between text-xs text-gray-600 mb-1">
                              <span>Progress</span>
                              <span>{project.progress.toFixed(0)}%</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div
                                className="bg-blue-600 h-2 rounded-full transition-all"
                                style={{ width: `${project.progress}%` }}
                              ></div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              📹 Upload Videos
            </h3>
            <p className="text-sm text-gray-500 mb-4">
              Upload multi-angle videos to create virtual environments
            </p>
            <Link
              href="/projects/new"
              className="text-blue-600 hover:text-blue-700 text-sm font-medium"
            >
              Get Started →
            </Link>
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              🤖 Train Robots
            </h3>
            <p className="text-sm text-gray-500 mb-4">
              Export datasets for humanoid robot training
            </p>
            <Link
              href="/datasets"
              className="text-blue-600 hover:text-blue-700 text-sm font-medium"
            >
              View Datasets →
            </Link>
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              🥽 VR Experience
            </h3>
            <p className="text-sm text-gray-500 mb-4">
              Relive memories in virtual reality with AI characters
            </p>
            <Link
              href="/vr"
              className="text-blue-600 hover:text-blue-700 text-sm font-medium"
            >
              Launch VR →
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}

// Made with Bob
