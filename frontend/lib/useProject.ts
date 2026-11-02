"use client";

import { useEffect, useState } from "react";
import { api } from "./api";
import type { Project } from "./types";

/** Project list plus the selected project (?project= in the URL, else the most recent). */
export function useProject() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [projectId, setProjectId] = useState("");
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    api<Project[]>("/projects").then((ps) => {
      setProjects(ps);
      const wanted = new URLSearchParams(window.location.search).get("project");
      setProjectId(ps.find((p) => p.id === wanted)?.id ?? ps[0]?.id ?? "");
    }).catch(setError);
  }, []);
  return { projects, projectId, setProjectId, error };
}
