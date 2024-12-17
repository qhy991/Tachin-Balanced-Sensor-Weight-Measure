import pyqtgraph.opengl as gl
import numpy as np

# Create a GLViewWidget
view = gl.GLViewWidget()
view.setCameraPosition(distance=50)

# Create a grid item and add it to the view
grid = gl.GLGridItem()
view.addItem(grid)

# Generate data for the surface plot
X, Y = np.meshgrid(range(10), range(10))
Z = np.sin(X) * np.cos(Y)

# Create a GLSurfacePlotItem and set its data
surface = gl.GLSurfacePlotItem(x=X, y=Y, z=Z, shader='heightColor', computeNormals=False, smooth=False)

# Add the surface plot item to the view
view.addItem(surface)