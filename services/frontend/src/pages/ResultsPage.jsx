import React from "react";
import SentimentChart from "../components/SentimentChart";
import PostCard from "../components/PostCard";
import "../index.css";

const ResultsPage = ({ results, onBack }) => {
  if (!results) return null; // si no hay resultados, no renderizamos nada

  // Generar array plano de posts con su sentimiento actual
  const posts = Object.entries(results).flatMap(([sentimentKey, data]) =>
    data.examples.map((example) => ({
      text: example,
      sentiment: sentimentKey, // veryNegative, negative, positive, veryPositive
    }))
  );

  return (
    <div className="results-page">
      <div className="header-bar">
        <button className="back-button" onClick={onBack}>
          ← Back
        </button>
      </div>

      {/* Gráfico de barras de porcentajes */}
      <SentimentChart data={results} />

      {/* Grid de posts con tarjetas y botones de corrección */}
      <div className="posts-grid">
        {posts.map((post, idx) => (
          <PostCard key={idx} text={post.text} sentiment={post.sentiment} />
        ))}
      </div>
    </div>
  );
};

export default ResultsPage;
