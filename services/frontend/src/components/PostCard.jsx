import React, { useState } from "react";
import { motion } from "framer-motion";

const sentimentColors = {
  veryNegative: "#ff4d4d",
  negative: "#ff944d",
  positive: "#4da6ff",
  veryPositive: "#33cc33",
};

const spaToEng = {
  "Muy Negativo": "veryNegative",
  "Negativo": "negative",
  "Positivo": "positive",
  "Muy Positivo": "veryPositive",
};

const engToSpa = {
  veryNegative: "Muy Negativo",
  negative: "Negativo",
  positive: "Positivo",
  veryPositive: "Muy Positivo",
};

const PostCard = ({ id, text, sentiment, score }) => {
  const [clicked, setClicked] = useState(false);
  const [selected, setSelected] = useState(null);

  const sendCorrection = async (corrected) => {
    if (clicked) return; // evita múltiples clicks
    setClicked(true);
    setSelected(corrected);

    try {
      await fetch("http://localhost:8000/correction", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          post_id: id,
          original_sentiment: sentiment,
          corrected_sentiment: corrected,
          text: text,
        }),
      });
    } catch (err) {
      console.error("Error enviando corrección:", err);
      setClicked(false); // permite reintentar en caso de error
      setSelected(null);
    }
  };

  return (
    <motion.div
      className="post-card"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <p className="post-text">{text}</p>

      {score !== undefined && (
        <p className="post-score">Sentimiento: {engToSpa[sentiment]}</p>
      )}

      <div className="post-card-buttons">
        {Object.keys(spaToEng).map((label) => {
          const key = spaToEng[label];
          const isSelected = selected === key;
          return (
            <button
              key={label}
              onClick={() => sendCorrection(key)}
              disabled={clicked}
              className={`correction-btn ${isSelected ? "selected " + key : ""}`}
            >
              {label}
            </button>
          );
        })}
      </div>
    </motion.div>
  );
};

export default PostCard;
