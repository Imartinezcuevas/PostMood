import React from "react";
import { motion } from "framer-motion";

const sentimentColors = {
  veryNegative: "#ff4d4d",
  negative: "#ff944d",
  positive: "#4da6ff",
  veryPositive: "#33cc33",
};

const PostCard = ({ text, sentiment }) => {
  return (
    <motion.div
      className="post-card"
      style={{ borderColor: sentimentColors[sentiment], backgroundColor: "#f5f5f5" }}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <p>{text}</p>
      <div className="post-card-buttons">
        <button className=".correction_btn">Muy Negativo</button>
        <button>Negativo</button>
        <button>Positivo</button>
        <button>Muy Positivo</button>
      </div>
    </motion.div>
  );
};

export default PostCard;
