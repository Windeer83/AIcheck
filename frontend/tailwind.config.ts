import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17211f",
        slate: "#54615f",
        line: "#dce5e2",
        panel: "#f7faf9",
        teal: "#087d74",
        amber: "#b96f08",
        danger: "#b3261e"
      },
      boxShadow: {
        soft: "0 18px 60px rgba(23, 33, 31, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;

