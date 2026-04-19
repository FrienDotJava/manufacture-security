"use client";

import { useState } from "react";
import { AnalysisResponse } from "./types/security";
import AnalysisResults from "./components/AnalysisResults";
import FlowGraph, { NodeRedNode } from "./components/FlowGraph";

// Force relative URLs in production builds
// Only use localhost when explicitly running in development mode
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === "development" &&
  typeof window !== "undefined" &&
  window.location?.hostname === "localhost"
    ? "http://localhost:8000"
    : "");

/**
 * Main application page for cybersecurity code analysis
 */
export default function Home() {
  const [analysisResults, setAnalysisResults] =
    useState<AnalysisResponse | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flowNodes, setFlowNodes] = useState<NodeRedNode[]>([]);

  const handleFetchFlow = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/flow`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const raw = Array.isArray(data)
        ? data
        : (data.flows ??
          data.nodes ??
          data.data ??
          Object.values(data).find(Array.isArray) ??
          []);

      const canvasNodes = raw.filter(
        (n: NodeRedNode) => typeof n.x === 'number' && typeof n.y === 'number'
      );

      setFlowNodes(canvasNodes);
    } catch (err) {
      console.error("Failed to load flow", err);
    }
  };

  const handleAnalyzeFlow = async () => {
    setIsAnalyzing(true);
    setError(null);

    try {
      await handleFetchFlow();
      const response = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const results: AnalysisResponse = await response.json();
      setAnalysisResults(results);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred during analysis",
      );
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleInjectAnalyzeFlow = async () => {
    setIsAnalyzing(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/fault-inject`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const results: AnalysisResponse = await response.json();
      setAnalysisResults(results);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred during analysis",
      );
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-foreground">
            Node-RED Security Analysis
          </h1>
          <p className="text-accent mt-2">
            Professional Node-RED flow analysis tool for security analysis
          </p>
        </header>
        <button
          onClick={handleAnalyzeFlow}
          disabled={isAnalyzing}
          className="mb-6 mr-6 bg-accent hover:bg-accent/90 disabled:bg-gray-400 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg transition-colors font-medium"
        >
          {isAnalyzing ? "Analyzing..." : "Fetch and Analyze Flow"}
        </button>
        <button
          onClick={handleInjectAnalyzeFlow}
          disabled={isAnalyzing}
          className="mb-6 bg-accent hover:bg-accent/90 disabled:bg-gray-400 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg transition-colors font-medium"
        >
          {isAnalyzing
            ? "Analyzing..."
            : "Inject Sensor Value and Analyze Flow"}
        </button>
        {flowNodes.length > 0 && (
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-foreground mb-3">
              Active Flow
            </h2>
            <FlowGraph
              nodes={flowNodes}
              highlightedNodeId={analysisResults?.issues?.[0]?.node_id}
            />
          </div>
        )}
        <div className="grid grid-rows-2 gap-6 h-fit">
          <AnalysisResults
            analysisResults={analysisResults}
            isAnalyzing={isAnalyzing}
            error={error}
          />
        </div>
      </div>
    </div>
  );
}
