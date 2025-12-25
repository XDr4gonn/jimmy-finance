import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches

class Cabinet:
    """
    A parametric cabinet class.
    Calculates its own cut list based on input dimensions.
    """
    def __init__(self, width, height=34.5, depth=24, name="Base Cabinet"):
        self.width = width
        self.height = height
        self.depth = depth
        self.name = name
        self.material_thickness = 0.75  # 3/4 inch plywood

    def get_cut_list(self):
        """Generates a list of parts with dimensions based on cabinet size."""
        t = self.material_thickness
        
        # Simplified "Frameless" construction logic
        parts = [
            {"Part": "Side Panel (L)", "H": self.height, "W": self.depth, "Qty": 1},
            {"Part": "Side Panel (R)", "H": self.height, "W": self.depth, "Qty": 1},
            {"Part": "Bottom Panel", "H": self.depth, "W": self.width - (2*t), "Qty": 1},
            {"Part": "Back Panel", "H": self.height, "W": self.width - (2*t), "Qty": 1},
            {"Part": "Toe Kick", "H": 4.5, "W": self.width, "Qty": 1},
            # Simple Door (assuming full overlay)
            {"Part": "Door", "H": self.height - 4.5, "W": self.width - 0.25, "Qty": 1},
        ]
        
        # Add Cabinet ID to each part
        for p in parts:
            p['Cabinet_ID'] = f"{self.name} ({self.width}\")"
            
        return parts

class KitchenDesigner:
    """
    The 'AI' engine. Uses a Greedy Algorithm to fill wall space.
    """
    def __init__(self, wall_length):
        self.wall_length = wall_length
        self.cabinets = []
        self.remaining_space = wall_length
        # Standard industry widths
        self.standard_sizes = [36, 33, 30, 27, 24, 21, 18, 15, 12, 9]

    def auto_fill_wall(self):
        """
        Iterates through standard sizes (largest to smallest)
        to fill the wall with the minimum number of cabinets.
        """
        print(f"--- Designing for Wall Length: {self.wall_length}\" ---")
        
        # Greedy Algorithm: Try to fit the largest cabinet possible first
        while self.remaining_space >= min(self.standard_sizes):
            for size in self.standard_sizes:
                if self.remaining_space >= size:
                    # Place cabinet
                    new_cab = Cabinet(width=size)
                    self.cabinets.append(new_cab)
                    self.remaining_space -= size
                    print(f"Placed {size}\" cabinet. Remaining: {self.remaining_space}\"")
                    break # Restart loop to try largest again
        
        if self.remaining_space > 0:
            print(f"Warning: {self.remaining_space}\" of filler space required.")

    def generate_master_cut_list(self):
        """Aggregates all parts from all cabinets into one DataFrame."""
        all_parts = []
        for cab in self.cabinets:
            all_parts.extend(cab.get_cut_list())
            
        df = pd.DataFrame(all_parts)
        return df

    def visualize_layout(self):
        """Draws a simple top-down 2D plan using Matplotlib."""
        fig, ax = plt.subplots(figsize=(12, 4))
        
        current_x = 0
        for cab in self.cabinets:
            # Create a rectangle for the cabinet
            rect = patches.Rectangle(
                (current_x, 0), cab.width, cab.depth, 
                linewidth=1, edgecolor='black', facecolor='#e0e0e0'
            )
            ax.add_patch(rect)
            
            # Add text label
            ax.text(
                current_x + cab.width/2, cab.depth/2, 
                f"{cab.width}\"", 
                ha='center', va='center', fontsize=10, weight='bold'
            )
            
            current_x += cab.width

        # Draw the filler strip if needed
        if self.remaining_space > 0:
            rect = patches.Rectangle(
                (current_x, 0), self.remaining_space, 24, 
                linewidth=1, edgecolor='red', facecolor='#ffcccc', hatch='//'
            )
            ax.add_patch(rect)
            ax.text(current_x + self.remaining_space/2, 12, "Filler", ha='center', fontsize=8, color='red')

        # Set plot limits
        ax.set_xlim(-5, self.wall_length + 5)
        ax.set_ylim(-5, 30) # Typical depth is 24, giving some buffer
        ax.set_aspect('equal')
        ax.set_title(f"Kitchen Layout (Wall: {self.wall_length}\")")
        ax.set_xlabel("Wall Distance (inches)")
        ax.set_ylabel("Depth (inches)")
        
        # Show specific elements
        plt.grid(True, which='both', linestyle='--', alpha=0.5)
        plt.show()

# --- RUNNING THE APP ---

# 1. Setup the Designer for a 115 inch wall
designer = KitchenDesigner(wall_length=115)

# 2. Run the "AI" to place cabinets
designer.auto_fill_wall()

# 3. Generate and showing the cut list
cut_list_df = designer.generate_master_cut_list()
print("\n--- MASTER CUT LIST (First 10 rows) ---")
print(cut_list_df.head(10))

# 4. Save to CSV (Optional)
# cut_list_df.to_csv("kitchen_project_cutlist.csv", index=False)

# 5. Show the blueprint
designer.visualize_layout()
