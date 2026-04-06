import { create } from "zustand";
import { rpc } from "../lib/rpc";
import type { Project } from "../lib/types";

interface ProjectState {
  projects: Project[];
  activeProject: Project | null;
  loading: boolean;
  loadProjects: () => Promise<void>;
  openProject: (path: string) => Promise<Project>;
  upsertProject: (project: Project) => void;
  setActiveProject: (project: Project | null) => void;
  setProjects: (projects: Project[]) => void;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  activeProject: null,
  loading: false,
  loadProjects: async () => {
    set({ loading: true });
    try {
      const result = await rpc<{ projects: Project[] }>("project.list");
      set({ projects: result.projects, loading: false });
      if (!get().activeProject && result.projects.length > 0) {
        set({ activeProject: result.projects[0] });
      }
    } catch {
      set({ loading: false });
    }
  },
  openProject: async (path: string) => {
    const project = await rpc<Project>("project.open", { path });
    set((state) => {
      const projects = state.projects.some((item) => item.path === project.path)
        ? state.projects.map((item) => (item.path === project.path ? project : item))
        : [project, ...state.projects];
      return { projects, activeProject: project };
    });
    return project;
  },
  upsertProject: (project) =>
    set((state) => ({
      projects: state.projects.some((item) => item.path === project.path)
        ? state.projects.map((item) => (item.path === project.path ? project : item))
        : [project, ...state.projects],
      activeProject: state.activeProject?.path === project.path ? project : state.activeProject,
    })),
  setActiveProject: (project) => set({ activeProject: project }),
  setProjects: (projects) =>
    set((state) => ({
      projects,
      activeProject: state.activeProject ?? projects[0] ?? null,
    })),
}));
