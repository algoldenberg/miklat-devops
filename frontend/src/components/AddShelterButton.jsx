// Ported verbatim from shelter-route-planner — trivial component, no data-shape
// dependency. CSS import removed: styles live in our combined index.css.

const AddShelterButton = ({ onClick }) => {
  return (
    <button className="add-shelter-btn" onClick={onClick} title="Suggest a new shelter">
      ➕
    </button>
  );
};

export default AddShelterButton;
