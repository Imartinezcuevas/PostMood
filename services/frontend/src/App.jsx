import React, { useState, useEffect } from "react";
import SearchPage from "./pages/SearchPage";
import ResultsPage from "./pages/ResultsPage";

function App() {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState(null);

  // Polling para comprobar estado del job
  useEffect(() => {
    if (!jobId) return;

    const interval = setInterval(async () => {
      try {
        const statusResp = await fetch(`http://localhost:8000/status/${jobId}`);
        const statusData = await statusResp.json();

        console.log("Polling status:", statusData);

        if (statusData.status === "done") {
          // El resultado viene en statusData.result que es el objeto completo que devuelve /analyze
          // Debemos acceder a statusData.result.data para obtener los sentimientos
          const sentimentData = statusData.result?.data || statusData.result;
          
          console.log("Sentiment data from polling:", sentimentData);

          const processedResults = {
            veryNegative: sentimentData.veryNegative || { percentage: 0, examples: [] },
            negative: sentimentData.negative || { percentage: 0, examples: [] },
            positive: sentimentData.positive || { percentage: 0, examples: [] },
            veryPositive: sentimentData.veryPositive || { percentage: 0, examples: [] },
          };

          setResults(processedResults);
          setLoading(false);
          setJobId(null);
          clearInterval(interval);
        } else if (statusData.status === "failed") {
          console.error("El análisis falló:", statusData.error);
          alert("El análisis falló. Por favor intenta de nuevo.");
          setLoading(false);
          setJobId(null);
          clearInterval(interval);
        }
      } catch (err) {
        console.error("Error obteniendo estado del job:", err);
        alert("Error al verificar el estado del análisis.");
        setLoading(false);
        setJobId(null);
        clearInterval(interval);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [jobId]);

  const handleSearch = async (keyword) => {
    setLoading(true);
    setResults(null);
    setJobId(null);

    try {
      const response = await fetch("http://localhost:8000/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword }),
      });

      if (!response.ok) {
        throw new Error(`Error en la petición: ${response.status}`);
      }

      const data = await response.json();
      console.log("Analyze response:", data);

      if (data.status === "done") {
        const sentimentData = data.data;

        console.log("Sentiment data from cache:", sentimentData);

        const processedResults = {
          veryNegative: sentimentData.veryNegative || { percentage: 0, examples: [] },
          negative: sentimentData.negative || { percentage: 0, examples: [] },
          positive: sentimentData.positive || { percentage: 0, examples: [] },
          veryPositive: sentimentData.veryPositive || { percentage: 0, examples: [] },
        };

        setResults(processedResults);
        setLoading(false);
      } else if (data.status === "queued") {
        console.log("Job queued, starting polling for job_id:", data.job_id);
        setJobId(data.job_id);
      } else {
        console.error("Estado inesperado:", data);
        alert("Respuesta inesperada del servidor.");
        setLoading(false);
      }
    } catch (err) {
      console.error("Error iniciando análisis:", err);
      alert("Error al iniciar el análisis. Por favor intenta de nuevo.");
      setLoading(false);
      setJobId(null);
    }
  };

  const handleBack = () => {
    setResults(null);
    setLoading(false);
    setJobId(null);
  };

  console.log("Current state - results:", results, "loading:", loading, "jobId:", jobId);

  return (
    <>
      {!results ? (
        <SearchPage onSearch={handleSearch} loading={loading} />
      ) : (
        <ResultsPage results={results} onBack={handleBack} />
      )}
    </>
  );
}

export default App;